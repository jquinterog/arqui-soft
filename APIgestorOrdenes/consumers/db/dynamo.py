"""
Acceso a DynamoDB: tablas orders, order_book, trades_by_order.
Incluye creación de tablas, persistencia y matching atómico con TransactWriteItems.
"""
import os
import uuid
import boto3

# Para ordenar BUY por precio descendente: priceKey = MAX - price_cents (ascending = mejor compra primero)
MAX_PRICE_CENTS = 10**12

# Estados de orden (engine)
ORDER_STATUS_OPEN = "OPEN"
ORDER_STATUS_PARTIAL = "PARTIAL"
ORDER_STATUS_FILLED = "FILLED"


def get_client(region: str, endpoint_url: str | None = None):
    url = endpoint_url or os.environ.get("AWS_ENDPOINT_URL") or None
    if isinstance(url, str):
        url = url.strip() or None
    kwargs = {"region_name": region}
    if url:
        kwargs["endpoint_url"] = url
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "test")
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
    return boto3.client("dynamodb", **kwargs)


def _n(val):
    """Decimal/num para DynamoDB."""
    if isinstance(val, (int, float)):
        return {"N": str(int(val) if isinstance(val, int) or val == int(val) else val)}
    return {"N": str(val)}


def _s(val):
    return {"S": str(val)}


def _b(val):
    return {"BOOL": bool(val)}


def _item_to_dict(item: dict) -> dict:
    result = {}
    for k, v in item.items():
        if "S" in v:
            result[k] = v["S"]
        elif "N" in v:
            n = v["N"]
            result[k] = float(n) if "." in n or "e" in n.lower() else int(n)
        elif "BOOL" in v:
            result[k] = v["BOOL"]
        else:
            result[k] = v
    return result


# --- Tabla orders ---

def ensure_orders_table(client, table_name: str):
    """Crea tabla orders: PK order_id, GSI1 (symbol, status#ts_ms#order_id)."""
    try:
        client.describe_table(TableName=table_name)
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "order_id", "AttributeType": "S"},
            {"AttributeName": "gsi1_pk", "AttributeType": "S"},
            {"AttributeName": "gsi1_sk", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "gsi1",
                "KeySchema": [
                    {"AttributeName": "gsi1_pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1_sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)


def ensure_order_book_table(client, table_name: str):
    """Crea tabla order_book: PK book (symbol#side), SK sk (priceKey#ts_ms#order_id)."""
    try:
        client.describe_table(TableName=table_name)
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "book", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "book", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)


def ensure_trades_by_order_table(client, table_name: str):
    """Crea tabla trades_by_order: PK order_id, SK ts_ms#trade_id."""
    try:
        client.describe_table(TableName=table_name)
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "order_id", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "order_id", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)


def _order_book_price_key(side: str, price_cents: int) -> int:
    """SELL: price_cents. BUY: MAX_PRICE_CENTS - price_cents (ascending = mejor precio primero)."""
    if side == "SELL":
        return price_cents
    return MAX_PRICE_CENTS - price_cents


def _order_book_sk(side: str, price_cents: int, ts_ms: int, order_id: str) -> str:
    pk = _order_book_price_key(side, price_cents)
    return f"{pk:012d}#{ts_ms}#{order_id}"


def put_order(
    client,
    orders_table: str,
    order_id: str,
    symbol: str,
    side: str,
    price_cents: int,
    qty: float,
    cliente_id: str,
    ts_ms: int,
) -> None:
    """Inserta orden en tabla orders (OPEN, remaining_qty=qty)."""
    gsi1_sk = f"{ORDER_STATUS_OPEN}#{ts_ms:020d}#{order_id}"
    client.put_item(
        TableName=orders_table,
        Item={
            "order_id": _s(order_id),
            "symbol": _s(symbol),
            "side": _s(side),
            "price_cents": _n(price_cents),
            "qty": _n(qty),
            "remaining_qty": _n(qty),
            "status": _s(ORDER_STATUS_OPEN),
            "matched": _b(False),
            "trades_count": _n(0),
            "cliente_id": _s(cliente_id),
            "ts_ms": _n(ts_ms),
            "gsi1_pk": _s(symbol),
            "gsi1_sk": _s(gsi1_sk),
        },
    )


def insert_order_book(
    client,
    order_book_table: str,
    symbol: str,
    side: str,
    price_cents: int,
    ts_ms: int,
    order_id: str,
    remaining_qty: float,
) -> None:
    """Inserta entrada en order_book. book=symbol#side, sk=priceKey#ts_ms#order_id."""
    book = f"{symbol}#{side}"
    sk = _order_book_sk(side, price_cents, ts_ms, order_id)
    client.put_item(
        TableName=order_book_table,
        Item={
            "book": _s(book),
            "sk": _s(sk),
            "order_id": _s(order_id),
            "remaining_qty": _n(remaining_qty),
            "price_cents": _n(price_cents),
            "ts_ms": _n(ts_ms),
        },
    )


def get_order(client, orders_table: str, order_id: str) -> dict | None:
    resp = client.get_item(
        TableName=orders_table,
        Key={"order_id": _s(order_id)},
    )
    item = resp.get("Item")
    return _item_to_dict(item) if item else None


def _update_order_status_attrs(status: str, remaining_qty: float, matched: bool, trades_count: int, gsi1_sk: str) -> dict:
    return {
        "status": _s(status),
        "remaining_qty": _n(remaining_qty),
        "matched": _b(matched),
        "trades_count": _n(trades_count),
        "gsi1_sk": _s(gsi1_sk),
    }


def query_orders(
    client,
    orders_table: str,
    symbol: str | None = None,
    status: str | None = None,
    matched: bool | None = None,
    limit: int = 100,
) -> list[dict]:
    """Lista órdenes. Si symbol está definido usa GSI; si no, Scan con filtros."""
    if symbol:
        # GSI: gsi1_pk = symbol, gsi1_sk begins_with status#
        key_cond = "gsi1_pk = :pk"
        expr_vals = {":pk": _s(symbol)}
        if status:
            key_cond += " AND begins_with(gsi1_sk, :sk_prefix)"
            expr_vals[":sk_prefix"] = _s(status + "#")
        resp = client.query(
            TableName=orders_table,
            IndexName="gsi1",
            KeyConditionExpression=key_cond,
            ExpressionAttributeValues=expr_vals,
            Limit=limit,
        )
        items = resp.get("Items", [])
    else:
        resp = client.scan(TableName=orders_table, Limit=limit)
        items = resp.get("Items", [])
    out = [_item_to_dict(i) for i in items]
    if matched is not None:
        out = [o for o in out if o.get("matched") == matched]
    if status and not symbol:
        out = [o for o in out if o.get("status") == status]
    return out[:limit]


def get_trades_by_order(client, trades_table: str, order_id: str, limit: int = 100) -> list[dict]:
    """Consulta trades_by_order por order_id."""
    resp = client.query(
        TableName=trades_table,
        KeyConditionExpression="order_id = :oid",
        ExpressionAttributeValues={":oid": _s(order_id)},
        Limit=limit,
    )
    return [_item_to_dict(i) for i in resp.get("Items", [])]


def get_best_counter_orders(
    client,
    order_book_table: str,
    symbol: str,
    side: str,
    our_price_cents: int,
    limit: int = 10,
) -> list[dict]:
    """
    Para nuestra orden (side), devuelve las mejores contraórdenes (FIFO por ts_ms).
    BUY busca SELL con price_cents <= our_price (ascending en order_book = menor precio primero).
    SELL busca BUY con price_cents >= our_price (ascending en order_book = mayor precio primero = menor priceKey).
    """
    counter_side = "SELL" if side == "BUY" else "BUY"
    book = f"{symbol}#{counter_side}"
    # sk = priceKey#ts_ms#order_id. Para incluir todos los que cumplan precio: sk <= bound.
    if counter_side == "SELL":
        max_key = _order_book_price_key("SELL", our_price_cents)
        sk_max = f"{max_key:012d}#99999999999999999999#zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
    else:
        max_key = _order_book_price_key("BUY", our_price_cents)
        sk_max = f"{max_key:012d}#99999999999999999999#zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
    resp = client.query(
        TableName=order_book_table,
        KeyConditionExpression="book = :b AND sk <= :sk_max",
        ExpressionAttributeValues={":b": _s(book), ":sk_max": _s(sk_max)},
        Limit=limit,
    )
    items = resp.get("Items", [])
    # Ordenar por sk ascending (ya viene así) y devolver con remaining_qty > 0
    out = []
    for i in items:
        d = _item_to_dict(i)
        if d.get("remaining_qty", 0) > 0:
            out.append(d)
    return out


def run_one_match(
    client,
    orders_table: str,
    order_book_table: str,
    trades_table: str,
    our_order_id: str,
    counter_order_id: str,
    symbol: str,
    our_side: str,
    counter_side: str,
    our_price_cents: int,
    counter_price_cents: int,
    our_ts_ms: int,
    counter_ts_ms: int,
    fill_qty: float,
    trade_ts_ms: int,
    trade_id: str,
) -> None:
    """
    Ejecuta un match parcial o total entre nuestra orden y una contraorden.
    TransactWriteItems: actualiza 2 órdenes, inserta 2 items en trades_by_order, actualiza/borra 2 en order_book.
    """
    our_sk_ob = _order_book_sk(our_side, our_price_cents, our_ts_ms, our_order_id)
    counter_sk_ob = _order_book_sk(counter_side, counter_price_cents, counter_ts_ms, counter_order_id)
    book_our = f"{symbol}#{our_side}"
    book_counter = f"{symbol}#{counter_side}"

    # Leer estado actual de ambas órdenes para remaining_qty y trades_count
    our_o = get_order(client, orders_table, our_order_id)
    counter_o = get_order(client, orders_table, counter_order_id)
    if not our_o or not counter_o:
        return
    our_rem = float(our_o.get("remaining_qty", 0))
    counter_rem = float(counter_o.get("remaining_qty", 0))
    our_tc = int(our_o.get("trades_count", 0))
    counter_tc = int(counter_o.get("trades_count", 0))

    our_new_rem = our_rem - fill_qty
    counter_new_rem = counter_rem - fill_qty
    our_status = ORDER_STATUS_FILLED if our_new_rem <= 0 else ORDER_STATUS_PARTIAL
    counter_status = ORDER_STATUS_FILLED if counter_new_rem <= 0 else ORDER_STATUS_PARTIAL
    our_matched = our_new_rem <= 0 or our_o.get("matched")
    counter_matched = counter_new_rem <= 0 or counter_o.get("matched")
    our_gsi = f"{our_status}#{our_ts_ms:020d}#{our_order_id}"
    counter_gsi = f"{counter_status}#{counter_ts_ms:020d}#{counter_order_id}"

    sk_trade = f"{trade_ts_ms}#{trade_id}"

    transact = [
        {
            "Update": {
                "TableName": orders_table,
                "Key": {"order_id": _s(our_order_id)},
                "UpdateExpression": "SET remaining_qty = :rq, #st = :st, matched = :m, trades_count = :tc, gsi1_sk = :gsi",
                "ExpressionAttributeNames": {"#st": "status"},
                "ExpressionAttributeValues": {
                    ":rq": _n(our_new_rem),
                    ":st": _s(our_status),
                    ":m": _b(our_matched),
                    ":tc": _n(our_tc + 1),
                    ":gsi": _s(our_gsi),
                },
            }
        },
        {
            "Update": {
                "TableName": orders_table,
                "Key": {"order_id": _s(counter_order_id)},
                "UpdateExpression": "SET remaining_qty = :rq, #st = :st, matched = :m, trades_count = :tc, gsi1_sk = :gsi",
                "ExpressionAttributeNames": {"#st": "status"},
                "ExpressionAttributeValues": {
                    ":rq": _n(counter_new_rem),
                    ":st": _s(counter_status),
                    ":m": _b(counter_matched),
                    ":tc": _n(counter_tc + 1),
                    ":gsi": _s(counter_gsi),
                },
            }
        },
        {
            "Put": {
                "TableName": trades_table,
                "Item": {
                    "order_id": _s(our_order_id),
                    "sk": _s(sk_trade),
                    "trade_id": _s(trade_id),
                    "buy_order_id": _s(our_order_id if our_side == "BUY" else counter_order_id),
                    "sell_order_id": _s(counter_order_id if our_side == "BUY" else our_order_id),
                    "qty": _n(fill_qty),
                    "price_cents": _n(counter_price_cents),
                    "ts_ms": _n(trade_ts_ms),
                },
            }
        },
        {
            "Put": {
                "TableName": trades_table,
                "Item": {
                    "order_id": _s(counter_order_id),
                    "sk": _s(sk_trade),
                    "trade_id": _s(trade_id),
                    "buy_order_id": _s(our_order_id if our_side == "BUY" else counter_order_id),
                    "sell_order_id": _s(counter_order_id if our_side == "BUY" else our_order_id),
                    "qty": _n(fill_qty),
                    "price_cents": _n(counter_price_cents),
                    "ts_ms": _n(trade_ts_ms),
                },
            }
        },
    ]

    # order_book: actualizar remaining_qty o borrar si 0
    if our_new_rem <= 0:
        transact.append({
            "Delete": {
                "TableName": order_book_table,
                "Key": {"book": _s(book_our), "sk": _s(our_sk_ob)},
            }
        })
    else:
        transact.append({
            "Update": {
                "TableName": order_book_table,
                "Key": {"book": _s(book_our), "sk": _s(our_sk_ob)},
                "UpdateExpression": "SET remaining_qty = :rq",
                "ExpressionAttributeValues": {":rq": _n(our_new_rem)},
            }
        })
    if counter_new_rem <= 0:
        transact.append({
            "Delete": {
                "TableName": order_book_table,
                "Key": {"book": _s(book_counter), "sk": _s(counter_sk_ob)},
            }
        })
    else:
        transact.append({
            "Update": {
                "TableName": order_book_table,
                "Key": {"book": _s(book_counter), "sk": _s(counter_sk_ob)},
                "UpdateExpression": "SET remaining_qty = :rq",
                "ExpressionAttributeValues": {":rq": _n(counter_new_rem)},
            }
        })

    items_for_transact = []
    for t in transact:
        if "Update" in t:
            items_for_transact.append({"Update": t["Update"]})
        elif "Put" in t:
            items_for_transact.append({"Put": t["Put"]})
        elif "Delete" in t:
            items_for_transact.append({"Delete": t["Delete"]})
    client.transact_write_items(TransactItems=items_for_transact)


def _transact_put_order_and_book(
    client,
    orders_table: str,
    order_book_table: str,
    order_id: str,
    symbol: str,
    side: str,
    price_cents: int,
    qty: float,
    cliente_id: str,
    ts_ms: int,
) -> None:
    """TransactWriteItems: insertar orden en orders y entrada en order_book atómicamente."""
    gsi1_sk = f"{ORDER_STATUS_OPEN}#{ts_ms:020d}#{order_id}"
    book = f"{symbol}#{side}"
    sk_ob = _order_book_sk(side, price_cents, ts_ms, order_id)
    client.transact_write_items(TransactItems=[
        {
            "Put": {
                "TableName": orders_table,
                "Item": {
                    "order_id": _s(order_id),
                    "symbol": _s(symbol),
                    "side": _s(side),
                    "price_cents": _n(price_cents),
                    "qty": _n(qty),
                    "remaining_qty": _n(qty),
                    "status": _s(ORDER_STATUS_OPEN),
                    "matched": _b(False),
                    "trades_count": _n(0),
                    "cliente_id": _s(cliente_id),
                    "ts_ms": _n(ts_ms),
                    "gsi1_pk": _s(symbol),
                    "gsi1_sk": _s(gsi1_sk),
                },
            }
        },
        {
            "Put": {
                "TableName": order_book_table,
                "Item": {
                    "book": _s(book),
                    "sk": _s(sk_ob),
                    "order_id": _s(order_id),
                    "remaining_qty": _n(qty),
                    "price_cents": _n(price_cents),
                    "ts_ms": _n(ts_ms),
                },
            }
        },
    ])


def run_order_accepted(
    client,
    orders_table: str,
    order_book_table: str,
    trades_table: str,
    order_id: str,
    symbol: str,
    side: str,
    price_cents: int,
    qty: float,
    cliente_id: str,
    ts_ms: int,
) -> None:
    """
    Persiste la orden + order_book en una transacción, luego ejecuta matching (FIFO, match parcial).
    TransactWriteItems para atomicidad en la primera escritura y en cada match.
    POC: replicas=1. Para escalar: lock por symbol (DynamoDB conditional write o Redis/DLM).
    """
    _transact_put_order_and_book(
        client, orders_table, order_book_table,
        order_id, symbol, side, price_cents, qty, cliente_id, ts_ms,
    )

    import time
    while True:
        our = get_order(client, orders_table, order_id)
        if not our:
            break
        our_rem = float(our.get("remaining_qty", 0))
        if our_rem <= 0:
            break
        counters = get_best_counter_orders(client, order_book_table, symbol, side, price_cents, limit=5)
        if not counters:
            break
        counter = counters[0]
        counter_rem = float(counter.get("remaining_qty", 0))
        if counter_rem <= 0:
            continue
        fill_qty = min(our_rem, counter_rem)
        if fill_qty <= 0:
            break
        trade_id = str(uuid.uuid4())
        trade_ts_ms = int(time.time() * 1000)
        run_one_match(
            client,
            orders_table,
            order_book_table,
            trades_table,
            our_order_id=order_id,
            counter_order_id=counter["order_id"],
            symbol=symbol,
            our_side=side,
            counter_side=counter_side_for(side),
            our_price_cents=price_cents,
            counter_price_cents=int(counter.get("price_cents", 0)),
            our_ts_ms=ts_ms,
            counter_ts_ms=int(counter.get("ts_ms", 0)),
            fill_qty=fill_qty,
            trade_ts_ms=trade_ts_ms,
            trade_id=trade_id,
        )


def counter_side_for(side: str) -> str:
    return "SELL" if side == "BUY" else "BUY"


# Compatibilidad con main.py que aún usa GET /ordenes (tabla antigua) y list_ordenes
def ensure_table(client, table_name: str):
    """Crea la tabla legacy 'ordenes' si no existe (para GET /ordenes que se mantiene)."""
    try:
        client.describe_table(TableName=table_name)
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)


def put_orden(client, table_name: str, payload: dict):
    """Legacy: guarda en tabla 'ordenes' antigua (por si algo aún la usa)."""
    from datetime import datetime
    ts = payload.get("timestamp")
    created_at = ts if isinstance(ts, str) else (datetime.utcnow().isoformat() + "Z")
    client.put_item(
        TableName=table_name,
        Item={
            "id": _s(payload["id"]),
            "tipo": _s(payload.get("tipo", payload.get("side", "compra"))),
            "activo": _s(payload.get("activo", payload.get("symbol", ""))),
            "cantidad": _n(payload.get("cantidad", payload.get("qty", 0))),
            "precio": _n(payload.get("precio", payload.get("price_cents", 0) / 100.0)),
            "cliente_id": _s(payload["cliente_id"]),
            "estado": _s("pendiente"),
            "created_at": _s(created_at),
        },
    )


def list_ordenes(client, table_name: str, limit: int = 100) -> list[dict]:
    """Legacy: scan tabla 'ordenes'."""
    resp = client.scan(TableName=table_name, Limit=limit)
    return [_item_to_dict(i) for i in resp.get("Items", [])]

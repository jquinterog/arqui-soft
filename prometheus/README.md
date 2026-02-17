# Prometheus

Query for the 95th percentile

```
1000 *
histogram_quantile(
  0.95,
  sum by (le) (
    rate(http_request_duration_seconds_bucket{path="/"}[30s])
  )
)
```

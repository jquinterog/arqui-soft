package main

import (
	"net/http"
	"orders-manager/controller"
)

func main() {
	router := controller.CreateRouter()
	http.ListenAndServe(":5000", router)
}

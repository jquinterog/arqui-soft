package controller

import (
	"math/rand"
	"net/http"
	"orders-manager/controller/metrics"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func CreateRouter() *chi.Mux {
	r := chi.NewRouter()
	r.Use(middleware.Logger)

	metrics.Init(prometheus.DefaultRegisterer)
	r.Use(metrics.Middleware)
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status": "OK"}`))
	})
	r.Handle("/metrics", promhttp.Handler())

	r.Get("/", func(w http.ResponseWriter, r *http.Request) {
		randomTimeout := rand.Intn(40) + 30
		time.Sleep(time.Duration(randomTimeout) * time.Millisecond)
		w.Write([]byte("welcome\n"))
	})
	return r
}

package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/prometheus/client_golang/prometheus"
)

var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "http_request_duration_seconds",
			Help: "HTTP request duration in seconds",
			Buckets: []float64{
				0.001, 0.0025, 0.005, 0.0075,
				0.01, 0.015, 0.02, 0.025,
				0.03, 0.04, 0.05, 0.06,
				0.07, 0.08, 0.09, 0.10,
				0.125, 0.15, 0.175, 0.2,
				0.25, 0.3, 0.4, 0.5,
				0.75, 1.0, 2.5, 5.0,
			},
		},
		[]string{"method", "path"},
	)
)

func Init(reg prometheus.Registerer) {
	reg.MustRegister(httpRequestsTotal, httpRequestDuration)
}

func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ww := chimw.NewWrapResponseWriter(w, r.ProtoMajor)

		start := time.Now()
		next.ServeHTTP(ww, r)

		route := chiRoutePattern(r)
		status := strconv.Itoa(ww.Status())

		httpRequestsTotal.WithLabelValues(r.Method, route, status).Inc()
		httpRequestDuration.WithLabelValues(r.Method, route).Observe(time.Since(start).Seconds())
	})
}

func chiRoutePattern(r *http.Request) string {
	if rctx := chi.RouteContext(r.Context()); rctx != nil {
		if pat := rctx.RoutePattern(); pat != "" {
			return pat
		}
	}
	return "unknown"
}

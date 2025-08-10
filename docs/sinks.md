Source of truth, from your code
FlinkStreamingJob → city_orders_per_minute
Columns: city_name, order_count, avg_delivery_time, window_start, window_end. Only Completed orders.

FlinkSlaMonitor → sla_violations + Kafka sla_violations
Columns: order_id, city_name, delivery_person_id, courier_name, delay_minutes. No timestamp column written.

DynamicSlaMonitor → dynamic_sla_violations, eta_model_performance
dynamic_sla_violations: order_id, predicted_minutes, actual_minutes, overrun_minutes, overrun_percentage, violation_timestamp.
eta_model_performance: order_id, predicted_minutes, actual_minutes, absolute_error.

SentimentAnalyzer → restaurant_live_sentiment, courier_live_sentiment
Restaurant: window_start, window_end, restaurant_id, review_count, avg_rating, pos_reviews, neg_reviews.
Courier: window_start, window_end, delivery_person_id, review_count, avg_rating, pos_reviews, neg_reviews.

WeatherAwareOrderAnalysisJob → order_weather_enriched + Kafka orders_enriched_weather
Columns include order_id, restaurant_id, city_id, event_time, weather... time_taken_minutes, hour_of_day....

CourierActivityJob → Kafka courier_features_live (upsert topic, no Postgres sink).

RestaurantStatusJob → Kafka restaurant_features_live (upsert topic, no Postgres sink).

eta_prediction_job.py → Kafka eta_predictions.
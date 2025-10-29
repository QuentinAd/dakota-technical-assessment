{% macro create_fct_energy_metrics_indexes() %}
  {% set sql %}
    CREATE INDEX IF NOT EXISTS idx_fct_energy_metrics_time_key ON marts.fct_energy_metrics (time_key);
    CREATE INDEX IF NOT EXISTS idx_fct_energy_metrics_location_key ON marts.fct_energy_metrics (location_key);
    CREATE INDEX IF NOT EXISTS idx_fct_energy_metrics_time_location ON marts.fct_energy_metrics (time_key, location_key);
    ALTER TABLE marts.fct_energy_metrics DROP CONSTRAINT IF EXISTS fk_fct_energy_metrics_time;
    ALTER TABLE marts.fct_energy_metrics DROP CONSTRAINT IF EXISTS fk_fct_energy_metrics_location;
    ALTER TABLE marts.fct_energy_metrics ADD CONSTRAINT fk_fct_energy_metrics_time FOREIGN KEY (time_key) REFERENCES marts.dim_time(time_key);
    ALTER TABLE marts.fct_energy_metrics ADD CONSTRAINT fk_fct_energy_metrics_location FOREIGN KEY (location_key) REFERENCES marts.dim_location(location_key);
  {% endset %}

  {% do run_query(sql) %}
  {% do log("Created indexes and constraints for fct_energy_metrics", info=True) %}
{% endmacro %}

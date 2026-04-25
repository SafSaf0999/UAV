FROM eclipse-mosquitto:2

# Install gettext for envsubst (used in entrypoint.sh to substitute env vars into config template)
USER root
RUN apk add --no-cache gettext

# Copy config template and entrypoint
COPY mosquitto.conf.template /mosquitto/config/mosquitto.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Mosquitto data directory for persistent message store
VOLUME ["/mosquitto/data", "/mosquitto/log"]

EXPOSE 8883

ENTRYPOINT ["/entrypoint.sh"]

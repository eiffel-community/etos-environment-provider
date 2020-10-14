#!/bin/bash

exec celery -A environment_provider.environment_provider.APP worker $CELERY_CMD_ARGS

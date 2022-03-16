export ETOS_GRAPHQL_SERVER="https://eiffel-er-sandbox.se.axis.com/graphql"
export ETOS_API="fake"                                                                                                            
export ETOS_ENVIRONMENT_PROVIDER="http://localhost:8001"
export ETOS_DATABASE_HOST=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' redis_redis-sentinel_1)                                                                                         
export ETOS_DATABASE_PASSWORD="str0ng_passw0rd"                
export ETOS_DATABASE_PORT="26379"
export CELERY_CMD_ARGS="-l DEBUG"

export ENVIRONMENT_PROVIDER_WAIT_FOR_IUT_TIMEOUT=10

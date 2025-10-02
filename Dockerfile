# Dockerfile to use with the controller environment where we run the environment provider as a Job
# instead of running it as an imported service in the suite runner.
FROM python:3.13-trixie AS build

COPY . /src
WORKDIR /src
RUN pip install --no-cache-dir build && python3 -m build

FROM python:3.13-slim-trixie

COPY --from=build /src/dist/*.whl /tmp
# hadolint ignore=DL3013

RUN pip install --no-cache-dir /tmp/*.whl && groupadd -r etos && useradd -r -m -s /bin/false -g etos etos

USER etos

LABEL org.opencontainers.image.source=https://github.com/eiffel-community/etos-environment-provider
LABEL org.opencontainers.image.authors=etos-maintainers@googlegroups.com
LABEL org.opencontainers.image.licenses=Apache-2.0

CMD ["python", "-u", "-m", "environment_provider.environment_provider"]

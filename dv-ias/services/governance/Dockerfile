ARG BASE=10.167.2.175:30500/szxc/base:1.1
FROM ${BASE}
ENV PYTHONPATH=/srv
WORKDIR /srv
COPY services/common/szxc_common /srv/szxc_common
COPY services/governance/app /srv/app
COPY services/governance/tests /srv/tests
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8083", "--workers", "2"]

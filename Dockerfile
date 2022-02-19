FROM kong/kong-gateway:2.5

# install python-pluginserver
USER root
# PYTHONWARNINGS=ignore is needed to build gevent on Python 3.9
RUN apk update && \
    apk add python3 py3-pip python3-dev musl-dev librdkafka-dev libffi-dev gcc g++ file make && \
    PYTHONWARNINGS=ignore pip3 install kong-pdk

COPY ./python-plugins/ /usr/local/kong/python-plugins

RUN pip3 install -r /usr/local/kong/python-plugins/requirements.txt

ENV term xterm
RUN apk add --update vim nano
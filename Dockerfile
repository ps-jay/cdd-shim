FROM python:2

MAINTAINER Philip Jay <phil@jay.id.au>

RUN pip install -U pip requests

RUN mkdir /opt/cdd-shim
ADD cdd-shim.py /opt/cdd-shim/

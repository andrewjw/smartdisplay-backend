FROM python:3.12-slim

ARG VERSION

RUN mkdir /display
COPY bin/ smartdisplay/ requirements.txt /display/
RUN pip3 install -r /display/requirements.txt

ENV PYTHONPATH=/display

ENTRYPOINT ["/display/bin/server"]
CMD []

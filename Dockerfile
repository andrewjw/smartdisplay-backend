FROM python:3.14-slim

ARG VERSION

RUN mkdir /display
COPY ./ /display/
RUN pip3 install -r /display/requirements.txt

ENV PYTHONPATH=/display

WORKDIR /display
ENTRYPOINT ["python3", "/display/bin/server.py"]
CMD []

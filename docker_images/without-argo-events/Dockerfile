FROM python:3.9-alpine

RUN set -ex && \
    apk add --no-cache gcc musl-dev

RUN mkdir /usr/src/app
WORKDIR /usr/src/app
COPY ./requirements.txt .
RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED 1

COPY . .

ENTRYPOINT [ "python", "app.py" ]
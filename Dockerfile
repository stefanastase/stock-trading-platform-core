# syntax=docker/dockerfile:1
FROM python:3.7-alpine
WORKDIR /code
RUN python -m pip install --upgrade pip


ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0


COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt 

EXPOSE 5000

COPY . .

CMD ["flask", "run"]
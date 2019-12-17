FROM python:3.7.3

ADD app.py requirements.txt conn_string.py /app/

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT [ "python", "app.py" ]





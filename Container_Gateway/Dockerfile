FROM python:3.7.3

ADD gateway.py requirements.txt conn_string.py page.html /app/

RUN pip install --no-cache-dir -r requirements.txt

ADD azure /root/.azure

WORKDIR /app

EXPOSE 8080

CMD ["python", "gateway.py"]

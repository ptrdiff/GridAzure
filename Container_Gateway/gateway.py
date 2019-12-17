import io
import json
import logging
import os
import sys
import uuid

import numpy as np
from azure.cli.core import get_default_cli
from azure.common import AzureConflictHttpError
from azure.servicebus import Message, QueueClient, ServiceBusClient
from flask import Flask, request, send_file
from PIL import Image

app = Flask(__name__)


def run_command(command):
    response = get_default_cli().invoke(command)
    return response


@app.route('/',  methods=["POST", "GET"])
def handle():
    if request.method == "POST":
        user_name = request.form.get("user_id")
        in_file = request.files['user_data']

        img = Image.open(io.BytesIO(in_file.read()))
        array = np.array(img.getdata()).reshape(img.size[0], img.size[1], 3)

        input_dict = {"auth_uid": user_name, "data": array.tolist()}

        update_access_token()
        doc_id = str(uuid.uuid4())

        create_recieve_queue(user_name, conn_string)
        send_to_mq(user_name, input_dict, conn_string)
        run_azure_start_container(conn_string, doc_id)
        result = wait_result(user_name, conn_string)
        delete_receive_queue(user_name, conn_string)
        run_azure_destroy_container(doc_id)

        img = Image.fromarray(result['result'])
        file_object = io.BytesIO()
        img.save(file_object, 'PNG')
        file_object.seek(0)

        return send_file(file_object, mimetype='image/PNG')

    elif request.method == "GET":
        with open('page.html') as html_page:
            return html_page.read()


def update_access_token():
    app_id = os.getenv("APP_ID")
    password = os.getenv("PASSWORD")
    tenant = os.getenv("TENANT")
    command = ["login","--service-principal","--username",f"{app_id}","--password",f"{password}","--tenant",f"{tenant}"]
    run_command(command)


def run_azure_start_container(conn_string, doc_id):
    command = ["webapp","create","-n",f"app-{doc_id}","-p","splan","-g","rgroup","-i","ptrdiff/segmentation",]
    try:
        run_command(command)
    except Exception:
        logging.error("Exception during container starting!")
        sys.exit(1)


def run_azure_destroy_container(doc_id):
    command = ["webapp","delete","-n",f"app-{doc_id}","-g","rgroup",]
    try:
        run_command(command)
    except Exception:
        logging.error("Exception during container destroying!")
        sys.exit(1)


def send_to_mq(auth_uid, message, conn_string):
    qс = QueueClient.from_connection_string(conn_string, auth_uid)
    json_message = Message(json.dumps(message).encode("utf-8"))
    qс.send(json_message)


def create_recieve_queue(auth_uid, conn_string):
    sbc = ServiceBusClient.from_connection_string(conn_string)
    try:
        sbc.create_queue(auth_uid)
    except AzureConflictHttpError: #drop random exception
        pass
    except Exception:
        logging.error("cannot create queue")
        sys.exit(1)


def delete_receive_queue(auth_uid, conn_string):
    sbc = ServiceBusClient.from_connection_string(conn_string)
    if not sbc.delete_queue(auth_uid):
        logging.error("Can not delete queue!")
        sys.exit(1)


def wait_result(auth_uid, conn_string):
    q = QueueClient.from_connection_string(conn_string, auth_uid)
    with q.get_receiver() as qr:
        messages = qr.fetch_next(timeout=30)
        message = str(messages[0])
        json_message = json.loads(message)
        return json_message


if __name__ == "__main__":
    from conn_string import conn_string
    try:
        create_recieve_queue('incoming', conn_string)
    except AzureConflictHttpError:
        pass
    app.config['DEBUG'] = True
    app.run(port=8080, host='0.0.0.0')

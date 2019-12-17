import json
import logging
import sys

import numpy as np
from azure.servicebus import Message, QueueClient

from scipy import ndimage as ndi
from skimage import color, feature, filters, measure, morphology, util


def seg(raw_image):
    image = color.rgb2gray(raw_image)
    image_blur = filters.gaussian(image, 5)
    sobel = filters.sobel(image_blur)
    image_u = util.img_as_ubyte(image_blur)

    local_otsu = filters.rank.otsu(image_u, morphology.square(15))
    mask = image_u >= local_otsu
    mask = morphology.binary_closing(mask, morphology.disk(3))
    mask = morphology.remove_small_holes(mask, area_threshold=64,
                                         connectivity=mask.ndim)
    mask[:, :int(mask.shape[1]*0.1)] = 0
    mask[:, -int(mask.shape[1]*0.1):] = 0

    distance = ndi.distance_transform_edt(image_blur)
    local_maxi = feature.peak_local_max(distance, labels=mask, indices=False)
    markers = measure.label(local_maxi)
    labels = morphology.watershed(sobel, markers, mask=mask)
    return labels


def get_message(channel, conn_string):
    qc = QueueClient.from_connection_string(conn_string, channel)
    with qc.get_receiver() as queue_receiver:
        messages = queue_receiver.fetch_next(timeout=30)
        message = str(messages[0])
        json_message = json.loads(message)
        return json_message


def send_message(channel, out_message, conn_string):
    qс = QueueClient.from_connection_string(conn_string, channel)
    json_message = Message(json.dumps(out_message).encode("utf-8"))
    qс.send(json_message)


if __name__ == "__main__":
    from conn_string import conn_string
    message = get_message("incoming", conn_string)

    try:
        out_channel_name = message["auth_uid"]
        data = np.fromlist(message["data"])
    except KeyError:
        logging.error("Request message key error!")
        sys.exit(1)

    try:
        result = seg(data)
    except Exception:
        logging.error("Exception during task!")
        sys.exit(1)

    out_message = {"result": result}
    send_message(out_channel_name, out_message, conn_string)
    sys.exit(0)

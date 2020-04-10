# USAGE
# python object_tracker.py --prototxt deploy.prototxt --model res10_300x300_ssd_iter_140000.caffemodel

# import the necessary packages
from pyimagesearch.centroidtracker import CentroidTracker
from scipy.spatial import distance as dist
from imutils.video import VideoStream
from beepy import beep
import numpy as np
import argparse
import imutils
import time
import cv2
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='hello')
close = False

def alert():
	beep(sound=1)

def midpoint(ptA, ptB):
	return ((ptA[0] + ptB[0]) * 0.5, (ptA[1] + ptB[1]) * 0.5)

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--prototxt", required=True,
	help="path to Caffe 'deploy' prototxt file")
ap.add_argument("-m", "--model", required=True,
	help="path to Caffe pre-trained model")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
	help="minimum probability to filter weak detections")
args = vars(ap.parse_args())

# initialize our centroid tracker and frame dimensions
ct = CentroidTracker()
(H, W) = (None, None)

# load our serialized model from disk
print("[INFO] loading model...")
net = cv2.dnn.readNetFromCaffe(args["prototxt"], args["model"])

# initialize the video stream and allow the camera sensor to warmup
print("[INFO] starting video stream...")
vs = VideoStream(src=0).start()
# vs = cv2.VideoCapture('run.mp4')
time.sleep(2.0)

# loop over the frames from the video stream
while True:
	# read the next frame from the video stream and resize it
	frame = vs.read()
	frame = imutils.resize(frame, width=400)

	# if the frame dimensions are None, grab them
	if W is None or H is None:
		(H, W) = frame.shape[:2]

	# construct a blob from the frame, pass it through the network,
	# obtain our output predictions, and initialize the list of
	# bounding box rectangles
	blob = cv2.dnn.blobFromImage(frame, 1.0, (W, H),
		(104.0, 177.0, 123.0))
	net.setInput(blob)
	detections = net.forward()
	rects = []

	# loop over the detections
	for i in range(0, detections.shape[2]):
		# filter out weak detections by ensuring the predicted
		# probability is greater than a minimum threshold
		if detections[0, 0, i, 2] > args["confidence"]:
			# compute the (x, y)-coordinates of the bounding box for
			# the object, then update the bounding box rectangles list
			box = detections[0, 0, i, 3:7] * np.array([W, H, W, H])
			rects.append(box.astype("int"))

			# draw a bounding box surrounding the object so we can
			# visualize it
			(startX, startY, endX, endY) = box.astype("int")
			cv2.rectangle(frame, (startX, startY), (endX, endY),
				(0, 255, 0), 2)

	# update our centroid tracker using the computed set of bounding
	# box rectangles
	objects = ct.update(rects)
	# loop over the tracked objects
	for (objectID, centroid) in objects.items():
		# draw both the ID of the object and the centroid of the
		# object on the output frame
		text = "ID {}".format(objectID)
		cv2.putText(frame, text, (centroid[0] - 10, centroid[1] - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
		cv2.circle(frame, (centroid[0], centroid[1]), 2, (0, 255, 0), -1)

	if len(objects) > 1:
		for i, (key_1, value_1) in enumerate(objects.items()):
			for j, (key_2, value_2) in enumerate(objects.items()):
				if i != j:
					object_1 = value_1
					object_2 = value_2
					if (object_1 is not None) and (object_2 is not None):
						xA = object_1[0]
						yA = object_1[1]
						xB = object_2[0]
						yB = object_2[1]
						D = dist.euclidean((xA, yA), (xB, yB))
						(mX, mY) = midpoint((xA, yA), (xB, yB))
						if D < 200.0:
							cv2.line(frame, (object_1[0], object_1[1]), (object_2[0], object_2[1]), (139,0,0),
									 thickness=1, lineType=8)
							cv2.putText(frame, "{:.1f}".format(D), (int(mX), int(mY - 10)),
										cv2.FONT_HERSHEY_SIMPLEX, 0.55, (139,0,0), 2)
							close = True
							body_str = str(key_1) + "," + str(key_2)
							channel.basic_publish(exchange='',
												  routing_key='hello',
												  body = body_str)
							# print(" [x] Sent 'Hello World!'")
						else:
							cv2.line(frame, (object_1[0], object_1[1]), (object_2[0], object_2[1]), (0, 255, 0),
									 thickness=1, lineType=8)
							cv2.putText(frame, "{:.1f}".format(D), (int(mX), int(mY - 10)),
										cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 0, 159), 2)
							close = False
					else:
						break
	# if close:
	# 	alert()
	people_count = len(objects)
	height, width, channels = frame.shape
	# print(height, width, people_count)
	# show the output frame
	cv2.imshow("Frame", frame)
	key = cv2.waitKey(1) & 0xFF

	# if the `q` key was pressed, break from the loop
	if key == ord("q"):
		break

# do a bit of cleanup
cv2.destroyAllWindows()
vs.stop()
connection.close()
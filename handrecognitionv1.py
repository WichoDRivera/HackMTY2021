import cv2
import mediapipe as mp

import pyautogui

from PIL import ImageGrab

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands


import tensorflow as tf
import os

graph_def = tf.compat.v1.GraphDef()
labels = []

# Helper Functions
def convert_to_opencv(image):
    # RGB -> BGR conversion is performed as well.
    image = image.convert('RGB')
    r,g,b = np.array(image).T
    opencv_image = np.array([b,g,r]).transpose()
    return opencv_image

def crop_center(img,cropx,cropy):
    h, w = img.shape[:2]
    startx = w//2-(cropx//2)
    starty = h//2-(cropy//2)
    return img[starty:starty+cropy, startx:startx+cropx]

def resize_down_to_1600_max_dim(image):
    h, w = image.shape[:2]
    if (h < 1600 and w < 1600):
        return image

    new_size = (1600 * w // h, 1600) if (h > w) else (1600, 1600 * h // w)
    return cv2.resize(image, new_size, interpolation = cv2.INTER_LINEAR)

def resize_to_256_square(image):
    h, w = image.shape[:2]
    return cv2.resize(image, (256, 256), interpolation = cv2.INTER_LINEAR)

def update_orientation(image):
    exif_orientation_tag = 0x0112
    if hasattr(image, '_getexif'):
        exif = image._getexif()
        if (exif != None and exif_orientation_tag in exif):
            orientation = exif.get(exif_orientation_tag, 1)
            # orientation is 1 based, shift to zero based and flip/transpose based on 0-based values
            orientation -= 1
            if orientation >= 4:
                image = image.transpose(Image.TRANSPOSE)
            if orientation == 2 or orientation == 3 or orientation == 6 or orientation == 7:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            if orientation == 1 or orientation == 2 or orientation == 5 or orientation == 6:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
    return image

# These are set to the default names from exported models, update as needed.
filename = "model.pb"
labels_filename = "labels.txt"

# Import the TF graph
with tf.io.gfile.GFile(filename, 'rb') as f:
    graph_def.ParseFromString(f.read())
    tf.import_graph_def(graph_def, name='')

# Create a list of labels.
with open(labels_filename, 'rt') as lf:
    for l in lf:
        labels.append(l.strip())

from PIL import Image
import numpy as np
import cv2

# For webcam input:
cap = cv2.VideoCapture(0)
idx = 1

with mp_hands.Hands(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5) as hands:
  while cap.isOpened():
    success, image = cap.read()
    if not success:
      print("Ignoring empty camera frame.")
      # If loading a video, use 'break' instead of 'continue'.
      continue

    # Flip the image horizontally for a later selfie-view display, and convert
    # the BGR image to RGB.
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    # To improve performance, optionally mark the image as not writeable to
    # pass by reference.
    image.flags.writeable = False
    results = hands.process(image)

    # Draw the hand annotations on the image.
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if results.multi_hand_landmarks:
      for hand_landmarks in results.multi_hand_landmarks:
        mp_drawing.draw_landmarks(
            image,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS,
            mp_drawing_styles.get_default_hand_landmarks_style(),
            mp_drawing_styles.get_default_hand_connections_style())
    cv2.imshow('Zoom', image)

    # Img save
    myScreenshot = pyautogui.screenshot()
    myScreenshot.save('my.png')
    image = Image.open('my.png')

    # Update orientation based on EXIF tags, if the file has orientation info.
    image = update_orientation(image)

    # Convert to OpenCV format
    image = convert_to_opencv(image)

    # If the image has either w or h greater than 1600 we resize it down respecting
    # aspect ratio such that the largest dimension is 1600
    image = resize_down_to_1600_max_dim(image)

    # We next get the largest center square
    h, w = image.shape[:2]
    min_dim = min(w,h)
    max_square_image = crop_center(image, min_dim, min_dim)

    # Resize that square down to 256x256
    augmented_image = resize_to_256_square(max_square_image)

    # Get the input size of the model
    with tf.compat.v1.Session() as sess:
        input_tensor_shape = sess.graph.get_tensor_by_name('Placeholder:0').shape.as_list()
    network_input_size = input_tensor_shape[1]

    # Crop the center for the specified network_input_Size
    augmented_image = crop_center(augmented_image, network_input_size, network_input_size)

    # These names are part of the model and cannot be changed.
    output_layer = 'loss:0'
    input_node = 'Placeholder:0'

    with tf.compat.v1.Session() as sess:
      try:
          prob_tensor = sess.graph.get_tensor_by_name(output_layer)
          predictions = sess.run(prob_tensor, {input_node: [augmented_image] })
      except KeyError:
          print ("Couldn't find classification output layer: " + output_layer + ".")
          print ("Verify this a model exported from an Object Detection project.")
          exit(-1)

    # Print the highest probability label
      highest_probability_index = np.argmax(predictions)
      print('Classified as: ' + labels[highest_probability_index])
      print()

    # Or you can print out all of the results mapping labels to probabilities.
      label_index = 0
      for p in predictions:
          truncated_probablity = np.float64(np.round(p,8))
          #print (labels[label_index], truncated_probablity)
          label_index += 1

    idx += 1
    font                   = cv2.FONT_HERSHEY_SIMPLEX
    bottomLeftCornerOfText = (70,450)
    fontScale              = 1
    fontColor              = (255,255,255)
    lineType               = 2
    cv2.putText(image, labels[highest_probability_index], bottomLeftCornerOfText, font, fontScale,fontColor,lineType)
  
    
    if cv2.waitKey(5) & 0xFF == 27:
      break
cap.release()

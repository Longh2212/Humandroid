from ultralytics import YOLO
import yaml

with open("/home/hhl/humandroid/config.yaml","r") as file:
    config = yaml.safe_load(file)

MODEL_PATH = config["location"]["model_path"]

class yoloCamera:
    def __init__(
        self,
        model_path=MODEL_PATH + "/yolov8n.pt",
        conf_threshold=0.5,
        cam0_id=0,
        cam1_id=1,
        resolution=(640, 480),
        rotate=True
        
    ):
        
        self.model =YOLO(model_path)
        self.conf_threshold =conf_threshold

    # -----------------
    # Detection
    # -----------------

    def detect(self, frame):
        results = self.model(frame,conf=self.conf_threshold,verbose=False)

        detections = []

        for result in results:

            for box in result.boxes:

                x1, y1, x2, y2 = (box.xyxy[0].cpu().numpy().astype(int))

                confidence = float(box.conf[0])

                class_id = int(box.cls[0])

                class_name = (self.model.names[class_id])

                center_x = (x1 + x2) / 2

                center_y = (y1 + y2) / 2

                detections.append(
                    {
                    "class_name":class_name,
                    "confidence":confidence,
                    "bbox":(x1,y1,x2,y2),
                    "center":(center_x,center_y)
                    }
                )

        return detections


    def human_face(self, detections):

        best_det = None
        best_confidence = 0

        for det in detections:
            if det["class_name"] != "person":
                continue

            if det["confidence"] > best_confidence:
                best_confidence = det["confidence"]
                best_det = det

        if best_det is None:
            return None

        x1, y1, x2, y2 = best_det["bbox"]
        cx, cy = best_det["center"]

        top_x = (x1 + x2) / 2
        top_y = y1

        face_x = (top_x + cx) / 2
        face_y = (top_y + cy) / 2

        return {
            "x": float(face_x),
            "y": float(face_y),
            "confidence": float(best_det["confidence"]),
            "bbox": best_det["bbox"]
        }
    
    def detect_obj(self, detections, obj_type):
        best_det = None
        best_confidence = 0
        best_area = 0

        for det in detections:
            if det["class_name"] != obj_type:
                continue

            x1, y1, x2, y2 = det["bbox"]
            area = (x2 - x1) * (y2 - y1)

            if det["confidence"] > best_confidence:
                best_confidence = det["confidence"]
                best_area = area
                best_det = det

        if best_det is None:
            return None

        x, y = best_det["center"]

        return {
            "obj": best_det["class_name"],
            "area": float(best_area),
            "x": float(x),
            "y": float(y),
            "confidence": float(best_det["confidence"]),
            "bbox": best_det["bbox"]
        }
    
    

    
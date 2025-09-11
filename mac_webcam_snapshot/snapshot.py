import os, sys, time

try:
    import cv2
except Exception as e:
    print("OpenCV (cv2) is not installed. Activate the venv and run: pip install opencv-python")
    sys.exit(1)


def main():
    device_index = int(os.getenv("WEBCAM_INDEX", "0"))
    output_name = os.getenv("OUTPUT", f"snapshot_{int(time.time())}.jpg")

    cap = cv2.VideoCapture(device_index)
    if not cap.isOpened():
        print(f"Failed to open webcam device index {device_index}")
        sys.exit(2)

    # Warm up camera on macOS for a brief moment
    time.sleep(0.2)

    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        print("Failed to capture frame from webcam")
        sys.exit(3)

    ok = cv2.imwrite(output_name, frame)
    if not ok:
        print(f"Failed to write image to {output_name}")
        sys.exit(4)

    print(f"Saved {output_name}")


if __name__ == "__main__":
    main()



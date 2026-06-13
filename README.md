# Hướng dẫn chạy ML Service - PC Hardware Bottleneck Classifier

Dịch vụ này cung cấp mô hình phân loại và API dự đoán nghẽn cổ chai của máy tính dựa trên các thuộc tính phần cứng (CPU, GPU, RAM, độ phân giải).

## 1. Cấu trúc dự án
- `app.py`: Máy chủ Flask API cung cấp endpoint dự đoán `/api/predict`.
- `training.ipynb`: Jupyter Notebook dùng để phân tích dữ liệu, huấn luyện mô hình Random Forest Classifier.
- `requirements.txt`: Danh sách thư viện Python cần cài đặt.
- `Dockerfile`: File cấu hình đóng gói ứng dụng với Docker.
- `static/`: Chứa các file mapping `cpu_dict.json` và `gpu_dict.json` để tra cứu điểm hiệu năng phần cứng.

---

## 2. Hướng dẫn chạy trên máy local

### Bước 1: Tạo môi trường ảo (Virtual Environment)
Mở terminal tại thư mục dự án và chạy các lệnh sau:
```bash
# Tạo môi trường ảo venv
python -m venv venv

# Kích hoạt môi trường ảo:
# Trên Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Trên Windows (CMD):
.\venv\Scripts\activate.bat
# Trên macOS/Linux:
source venv/bin/activate
```

### Bước 2: Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```

### Bước 3: Huấn luyện mô hình (Tùy chọn)
Nếu bạn muốn tự chạy lại quy trình huấn luyện và xuất mô hình:
1. Đảm bảo đã có file dữ liệu huấn luyện `bottleneck_dataset.csv`.
2. Mở file `training.ipynb` bằng VS Code hoặc Jupyter Notebook.
3. Chọn kernel của môi trường ảo `venv` vừa tạo.
4. Chạy toàn bộ các cell trong Notebook. Sau khi chạy xong, mô hình phân loại sẽ được lưu thành tệp `bottleneck_rf_model.joblib`.

### Bước 4: Khởi động Flask API Server
```bash
python app.py
```
Mặc định máy chủ sẽ chạy tại địa chỉ: `http://localhost:5000`

---

## 3. Cách thức hoạt động và kiểm thử API

### Endpoint: `/api/predict`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`
- **Body mẫu (JSON):**
```json
{
  "cpu_name": "Intel Core i3-12100F",
  "gpu_name": "NVIDIA RTX 5090",
  "ram_capacity": 16,
  "ram_bus_speed": 3200
}
```

- **Phản hồi mẫu (JSON):**
Trả về dự báo chi tiết cho 3 độ phân giải (1080p, 1440p, 2160p):
```json
{
  "success": true,
  "predictions": [
    {
      "resolution": "1080",
      "resolution_label": "1920x1080",
      "predicted_type": 1,
      "probability": 0.96,
      "probabilities": [0.04, 0.96, 0.0, 0.0],
      "explanation": "CPU Bottleneck: At this resolution, the CPU single-core speed runs at maximum capacity while the GPU waits. Consider upgrading the processor."
    },
    ...
  ]
}
```

---

## 4. Hướng dẫn chạy bằng Docker (Container)

Nếu muốn đóng gói dịch vụ thành Docker container:

### Bước 1: Build Docker Image
```bash
docker build -t ml-service .
```

### Bước 2: Khởi chạy Container
```bash
docker run -d -p 5000:5000 --name ml-server-container ml-service
```
Dịch vụ Flask API sẽ chạy bên trong container và được chuyển tiếp qua cổng `5000` ở máy chủ chính của bạn.

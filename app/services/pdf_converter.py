import os
import uuid
from typing import List, Tuple, Optional
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np


class PDFConverter:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)

    def otsu_threshold(self, gray_array: np.ndarray) -> int:
        """使用 Otsu 算法计算最佳二值化阈值
        
        Otsu 算法通过最大化类间方差来找到最佳阈值，
        能够更好地保留文字和细节。
        """
        # 计算灰度直方图
        histogram, _ = np.histogram(gray_array.flatten(), bins=256, range=(0, 256))
        total_pixels = gray_array.size
        
        # 归一化直方图
        histogram = histogram.astype(float) / total_pixels
        
        best_threshold = 0
        max_variance = 0
        
        # 累积和
        cumsum = np.cumsum(histogram)
        cumsum_mean = np.cumsum(histogram * np.arange(256))
        
        global_mean = cumsum_mean[-1]
        
        for t in range(1, 256):
            # 背景类权重和均值
            w0 = cumsum[t]
            if w0 == 0 or w0 == 1:
                continue
            
            w1 = 1 - w0
            
            # 背景和前景的均值
            mu0 = cumsum_mean[t] / w0
            mu1 = (global_mean - cumsum_mean[t]) / w1
            
            # 类间方差
            variance = w0 * w1 * (mu0 - mu1) ** 2
            
            if variance > max_variance:
                max_variance = variance
                best_threshold = t
        
        return best_threshold

    def kmeans_quantize(self, gray_array: np.ndarray, n_levels: int) -> Tuple[np.ndarray, np.ndarray]:
        """使用 K-means 聚类进行灰度量化
        
        K-means 会根据图像实际的灰度分布找到最佳的色阶中心，
        比简单的均匀量化更能保留图像细节。
        
        Args:
            gray_array: 灰度图像数组
            n_levels: 色阶数（例如 2档=3色阶）
            
        Returns:
            quantized_array: 量化后的图像数组
            centers: 聚类中心（色阶值）
        """
        # 展平数据用于聚类
        pixels = gray_array.flatten().astype(float)
        
        # 初始化聚类中心（均匀分布）
        centers = np.linspace(0, 255, n_levels)
        
        # 迭代 K-means
        for _ in range(20):  # 最多迭代20次
            # 分配每个像素到最近的中心
            distances = np.abs(pixels[:, np.newaxis] - centers)
            labels = np.argmin(distances, axis=1)
            
            # 更新中心
            new_centers = np.array([
                pixels[labels == i].mean() if np.sum(labels == i) > 0 else centers[i]
                for i in range(n_levels)
            ])
            
            # 检查收敛
            if np.allclose(centers, new_centers, atol=0.5):
                break
            centers = new_centers
        
        # 将中心四舍五入并排序
        centers = np.sort(np.round(centers).astype(int))
        centers = np.clip(centers, 0, 255)
        
        # 量化：将每个像素替换为最近的中心值
        distances = np.abs(pixels[:, np.newaxis] - centers)
        labels = np.argmin(distances, axis=1)
        quantized_pixels = centers[labels]
        
        return quantized_pixels.reshape(gray_array.shape).astype(np.uint8), centers

    def convert_image_to_grayscale(self, image: Image.Image, gray_levels: int) -> Image.Image:
        """将 PIL 图像转换为量化灰度图
        
        Args:
            image: 输入图像
            gray_levels: 灰度档位 (1-4)
                - 1档: 纯黑白 (2色阶)，使用 Otsu 算法
                - 2档: 3色阶，使用 K-means
                - 3档: 4色阶，使用 K-means
                - 4档: 5色阶，使用 K-means
        """
        # 转换为灰度图
        if image.mode != 'L':
            image = image.convert('L')
        
        # 转换为 numpy 数组
        gray_array = np.array(image)
        
        if gray_levels == 1:
            # 1档: 使用 Otsu 算法进行二值化
            threshold = self.otsu_threshold(gray_array)
            quantized_array = np.where(gray_array > threshold, 255, 0).astype(np.uint8)
        else:
            # 2-4档: 使用 K-means 聚类
            n_levels = gray_levels + 1  # 档位 + 1 = 色阶数
            quantized_array, _ = self.kmeans_quantize(gray_array, n_levels)
        
        # 转回 PIL Image
        quantized_image = Image.fromarray(quantized_array, mode='L')
        
        return quantized_image

    def extract_pdf_page_as_image(self, pdf_path: str, page_num: int, zoom: float = 2.0, keep_color: bool = False) -> Image.Image:
        """Extract PDF page as PIL Image
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)
            zoom: Zoom factor for resolution
            keep_color: If True, keep original colors (RGB). If False, convert to grayscale.
        """
        doc = fitz.open(pdf_path)
        page = doc[page_num]

        # Set zoom factor for higher resolution
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("ppm")
        img = Image.open(io.BytesIO(img_data))

        doc.close()
        
        # Convert to RGB to ensure color is preserved when needed
        if keep_color and img.mode != 'RGB':
            img = img.convert('RGB')
        
        return img
    
    def extract_pdf_page_color(self, pdf_path: str, page_num: int, zoom: float = 2.0) -> Image.Image:
        """Extract PDF page as color PIL Image (preserving original colors)"""
        return self.extract_pdf_page_as_image(pdf_path, page_num, zoom, keep_color=True)

    def convert_pdf_page_to_grayscale(self, pdf_path: str, page_num: int, gray_levels: int, zoom: float = 2.0) -> Image.Image:
        """Convert single PDF page to grayscale image"""
        # Extract page as image
        image = self.extract_pdf_page_as_image(pdf_path, page_num, zoom)

        # Convert to quantized grayscale
        grayscale_image = self.convert_image_to_grayscale(image, gray_levels)

        return grayscale_image

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Get total number of pages in PDF"""
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        doc.close()
        return page_count

    def create_grayscale_pdf(self, pdf_path: str, output_path: str, gray_levels: int) -> str:
        """Convert entire PDF to grayscale PDF"""
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get page dimensions
            rect = page.rect

            # Extract page as image with high resolution
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))

            # Convert to quantized grayscale
            grayscale_img = self.convert_image_to_grayscale(img, gray_levels)

            # Convert back to PDF page
            img_byte_arr = io.BytesIO()
            grayscale_img.save(img_byte_arr, format='PDF')
            img_byte_arr.seek(0)

            # Insert grayscale image into PDF
            img_doc = fitz.open("pdf", img_byte_arr.read())
            img_page = img_doc[0]

            # Scale to original page size
            img_rect = img_page.rect
            scale_x = rect.width / img_rect.width
            scale_y = rect.height / img_rect.height

            page.show_pdf_page(rect, img_doc, 0, keep_proportion=False)

            img_doc.close()

        # Save grayscale PDF
        doc.save(output_path)
        doc.close()

        return output_path

    async def convert_pdf_async(self, pdf_path: str, output_path: str, gray_levels: int) -> str:
        """Asynchronously convert PDF to grayscale"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.create_grayscale_pdf,
            pdf_path,
            output_path,
            gray_levels
        )

    def validate_pdf(self, file_path: str) -> bool:
        """Validate if file is a valid PDF"""
        try:
            doc = fitz.open(file_path)
            doc.close()
            return True
        except Exception:
            return False

    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        return os.path.getsize(file_path)

    def generate_task_id(self) -> str:
        """Generate unique task ID"""
        return str(uuid.uuid4())

    def cleanup_old_files(self, directory: str, max_age_hours: int = 1):
        """Clean up old files in directory"""
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for file_path in Path(directory).glob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                    except Exception:
                        pass
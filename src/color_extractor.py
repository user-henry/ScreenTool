"""
颜色提取模块
- 从 PIL Image 中提取主要颜色
- 使用 K-means 聚类 + 相近颜色合并
- 返回前 N 种主色（HEX 码 + RGB 值）
"""
import numpy as np
from PIL import Image
from collections import Counter


def _rgb_distance(c1, c2):
    """两个 RGB 颜色之间的欧氏距离"""
    return np.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))


def _kmeans_colors(pixels: np.ndarray, k: int = 8, max_iter: int = 20) -> list:
    """
    对像素数组做 K-means 聚类，返回 k 个聚类中心（RGB 元组）
    pixels: shape (N, 3)，每行是 (R, G, B)
    """
    n = len(pixels)
    if n <= k:
        # 像素数 ≤ k，直接返回所有唯一颜色
        unique = np.unique(pixels, axis=0)
        return [tuple(c) for c in unique]

    # 随机初始化 k 个中心
    indices = np.random.choice(n, k, replace=False)
    centroids = pixels[indices].astype(np.float64)

    for _ in range(max_iter):
        # 分配：每个像素到最近的中心
        distances = np.sqrt(((pixels[:, np.newaxis, :] - centroids[np.newaxis, :, :]) ** 2).sum(axis=2))
        labels = np.argmin(distances, axis=1)

        # 更新中心
        new_centroids = np.array([
            pixels[labels == i].mean(axis=0) if np.any(labels == i) else centroids[i]
            for i in range(k)
        ])

        if np.allclose(centroids, new_centroids, rtol=1e-4):
            break
        centroids = new_centroids

    # 转为整数 RGB
    return [tuple(np.round(c).astype(int)) for c in centroids]


def _merge_similar_colors(colors_with_counts: list, threshold: float = 35.0) -> list:
    """
    合并相近颜色（距离 < threshold），按加权平均合并，保留数量更大的
    输入：[((r,g,b), count), ...]
    输出：[((r,g,b), count), ...]
    """
    if len(colors_with_counts) <= 1:
        return colors_with_counts

    merged = []
    used = [False] * len(colors_with_counts)

    for i, (color_i, count_i) in enumerate(colors_with_counts):
        if used[i]:
            continue
        total_r, total_g, total_b = color_i[0] * count_i, color_i[1] * count_i, color_i[2] * count_i
        total_count = count_i

        for j in range(i + 1, len(colors_with_counts)):
            if used[j]:
                continue
            color_j, count_j = colors_with_counts[j]
            if _rgb_distance(color_i, color_j) < threshold:
                total_r += color_j[0] * count_j
                total_g += color_j[1] * count_j
                total_b += color_j[2] * count_j
                total_count += count_j
                used[j] = True

        avg_color = (
            round(total_r / total_count),
            round(total_g / total_count),
            round(total_b / total_count),
        )
        merged.append((avg_color, total_count))
        used[i] = True

    return merged


def _rgb_to_hex(rgb: tuple) -> str:
    """RGB 元组转 HEX 字符串，如 '#FF5733'"""
    return '#{:02X}{:02X}{:02X}'.format(*rgb)


def extract_colors(
    image: Image.Image,
    max_colors: int = 8,
    sample_step: int = 3,
    merge_threshold: float = 35.0,
) -> list:
    """
    从图像中提取主要颜色

    Args:
        image: PIL Image 对象
        max_colors: 最终返回的颜色数量上限
        sample_step: 采样步长（每隔 N 个像素取一个，加速处理）
        merge_threshold: 相近颜色合并的 RGB 距离阈值

    Returns:
        [{"hex": "#FF5733", "rgb": (255, 87, 51), "pct": 35.2}, ...]
        按像素占比降序排列
    """
    img = image.convert("RGB")

    # 缩放大图以加速
    w, h = img.size
    if w * h > 500000:  # > 50万像素，缩放
        scale = (500000 / (w * h)) ** 0.5
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # 采样像素
    pixels = []
    arr = np.array(img)
    for y in range(0, arr.shape[0], sample_step):
        for x in range(0, arr.shape[1], sample_step):
            pixels.append(arr[y, x])

    if not pixels:
        return []

    pixels = np.array(pixels, dtype=np.uint8)

    # K-means 聚类
    k = min(max_colors * 2, len(np.unique(pixels, axis=0)))  # 多聚一些再合并
    cluster_centers = _kmeans_colors(pixels, k=k)

    # 统计每个聚类中心的像素数（分配所有采样像素）
    centers_arr = np.array(cluster_centers, dtype=np.float64)
    distances = np.sqrt(((pixels[:, np.newaxis, :] - centers_arr[np.newaxis, :, :]) ** 2).sum(axis=2))
    labels = np.argmin(distances, axis=1)
    label_counts = Counter(labels.tolist())

    colors_with_counts = [(cluster_centers[i], label_counts.get(i, 0)) for i in range(len(cluster_centers))]
    colors_with_counts.sort(key=lambda x: x[1], reverse=True)

    # 合并相近颜色
    merged = _merge_similar_colors(colors_with_counts, threshold=merge_threshold)
    merged.sort(key=lambda x: x[1], reverse=True)

    # 截取前 max_colors，计算百分比
    total = sum(c for _, c in merged)
    result = []
    for rgb, count in merged[:max_colors]:
        result.append({
            "hex": _rgb_to_hex(rgb),
            "rgb": (int(rgb[0]), int(rgb[1]), int(rgb[2])),
            "pct": round(count / total * 100, 1) if total > 0 else 0,
        })

    return result

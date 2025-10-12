#!/usr/bin/env python3
"""
Fix PNG images by converting checkerboard patterns to actual transparency.
Uses a more sophisticated approach to detect checkerboard patterns.
"""
import numpy as np
from PIL import Image


def detect_checkerboard_pattern(rgb):
    """
    Detect checkerboard by looking for alternating light/dark pattern.
    Returns a mask of pixels that are part of the checkerboard.
    """
    light_gray = np.array([204, 204, 204])
    white = np.array([255, 255, 255])
    
    # Very tight threshold for exact matches only
    dist_to_light_gray = np.sqrt(np.sum((rgb - light_gray) ** 2, axis=2))
    dist_to_white = np.sqrt(np.sum((rgb - white) ** 2, axis=2))
    
    threshold = 5  # Very strict matching
    
    is_light_gray = dist_to_light_gray < threshold
    is_white = dist_to_white < threshold
    
    # Check for checkerboard pattern by looking at neighboring pixels
    height, width = is_light_gray.shape
    is_checkerboard = np.zeros((height, width), dtype=bool)
    
    # For each pixel, check if it's part of an alternating pattern
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if is_light_gray[y, x] or is_white[y, x]:
                # Check if neighbors alternate between light gray and white
                neighbors = [
                    (is_light_gray[y-1, x] or is_white[y-1, x]),
                    (is_light_gray[y+1, x] or is_white[y+1, x]),
                    (is_light_gray[y, x-1] or is_white[y, x-1]),
                    (is_light_gray[y, x+1] or is_white[y, x+1])
                ]
                # If surrounded by similar checkerboard colors, it's background
                if sum(neighbors) >= 3:
                    is_checkerboard[y, x] = True
    
    return is_checkerboard

def fix_transparency(input_path, output_path):
    """
    Convert checkerboard pattern to actual transparency.
    """
    img = Image.open(input_path).convert('RGBA')
    data = np.array(img)
    
    # Get RGB and alpha channels
    rgb = data[:, :, :3]
    alpha = data[:, :, 3]
    
    # Detect checkerboard pattern
    is_checkerboard = detect_checkerboard_pattern(rgb)
    
    # Set alpha to 0 for checkerboard pixels
    alpha[is_checkerboard] = 0
    
    # Update alpha channel
    data[:, :, 3] = alpha
    
    # Create new image with fixed alpha
    result = Image.fromarray(data, 'RGBA')
    result.save(output_path, 'PNG')
    print(f"Fixed: {input_path} -> {output_path}")

if __name__ == '__main__':
    # Fix the bookend images
    fix_transparency(
        'frontend/public/images/icons/warrior-bookend-left-transparent.png',
        'frontend/public/images/icons/warrior-bookend-left-transparent.png'
    )
    fix_transparency(
        'frontend/public/images/icons/warrior-bookend-right-transparent.png',
        'frontend/public/images/icons/warrior-bookend-right-transparent.png'
    )
    print("Done! Images fixed.")

/**
 * Data Bucketing/Aggregation Module
 * 
 * PURPOSE:
 * Combines raw elevation pixels into larger "buckets" for performance optimization.
 * Instead of rendering every pixel as a separate 3D bar, this groups NxN pixels into
 * one bucket and applies an aggregation method (MAX, AVERAGE, MIN, MEDIAN).
 * 
 * PERFORMANCE IMPACT:
 * - Bucket size 1x = full resolution (slowest, highest detail)
 * - Bucket size 10x = 100x fewer objects to render (much faster)
 * 
 * USAGE:
 * Called automatically during terrain creation and resolution changes.
 * The bucketing parameters are stored in global `params` object.
 * 
 * NOTE: This module depends on global variables (rawElevationData, params) for performance.
 * This is intentional to avoid excessive parameter passing in hot paths.
 */

/**
* Rebucket raw elevation data
* @param {Object} rawElevationData - Raw elevation data with width, height, elevation array
* @param {Object} params - Parameters including bucketSize (integer multiplier)
* @returns {Object} Processed data with bucketed elevation grid
*/
function rebucketData(rawElevationData, params) {
    const startTime = performance.now();

    const { width, height, elevation, bounds } = rawElevationData;

    // Calculate real-world scale
    const scale = calculateRealWorldScale(rawElevationData);

    // CORRECT APPROACH: Bucket size MUST be an integer multiple of pixel spacing
    // This ensures buckets align perfectly with the data grid
    const bucketSize = params.bucketSize; // Integer multiple (1, 2, 3, 4, ...)

    // Calculate bucketed dimensions (simple integer division)
    const bucketedWidth = Math.floor(width / bucketSize);
    const bucketedHeight = Math.floor(height / bucketSize);

    // Bucket physical size = pixel spacing x multiplier
    const bucketSizeMetersX = scale.metersPerPixelX * bucketSize;
    const bucketSizeMetersY = scale.metersPerPixelY * bucketSize;

    // Format pixel size with km if >1000m, one decimal point only
    function formatPixelSize(meters) {
        if (meters >= 1000) {
            return `${(meters / 1000).toFixed(1)}km`;
        } else {
            return `${meters.toFixed(1)}m`;
        }
    }
    console.log(` Raw data: ${width}x${height} pixels @ ${formatPixelSize(scale.metersPerPixelX)}x${formatPixelSize(scale.metersPerPixelY)}/pixel`);
    console.log(` Bucket multiplier: ${bucketSize}x -> ${bucketedWidth}x${bucketedHeight} buckets`);
    console.log(` Bucket size: ${(bucketSizeMetersX / 1000).toFixed(2)}km x ${(bucketSizeMetersY / 1000).toFixed(2)}km`);

    // Pre-allocate array for better performance
    const bucketedElevation = new Array(bucketedHeight);

    // Pre-allocate buffer for collecting values
    const maxBucketPixels = Math.ceil(bucketSize * bucketSize * 1.5); // 1.5x safety margin
    const buffer = new Float32Array(maxBucketPixels);

    for (let by = 0; by < bucketedHeight; by++) {
        const row = new Array(bucketedWidth);

        for (let bx = 0; bx < bucketedWidth; bx++) {
            // Calculate pixel range for this bucket (now always integer aligned)
            const pixelX0 = bx * bucketSize;
            const pixelX1 = (bx + 1) * bucketSize;
            const pixelY0 = by * bucketSize;
            const pixelY1 = (by + 1) * bucketSize;

            // Collect all values in this bucket (bucketSize x bucketSize pixels)
            let count = 0;
            for (let py = pixelY0; py < pixelY1 && py < height; py++) {
                for (let px = pixelX0; px < pixelX1 && px < width; px++) {
                    const val = elevation[py] && elevation[py][px];
                    if (val !== null && val !== undefined) {
                        buffer[count++] = val;
                    }
                }
            }

            // Aggregate based on method
            let value = null;
            if (count > 0) {
                switch (params.aggregation) {
                    case 'max':
                        value = buffer[0];
                        for (let i = 1; i < count; i++) {
                            if (buffer[i] > value) value = buffer[i];
                        }
                        break;
                    case 'min':
                        value = buffer[0];
                        for (let i = 1; i < count; i++) {
                            if (buffer[i] < value) value = buffer[i];
                        }
                        break;
                    case 'average':
                        value = 0;
                        for (let i = 0; i < count; i++) {
                            value += buffer[i];
                        }
                        value /= count;
                        break;
                    case 'median':
                        const sortedSlice = Array.from(buffer.slice(0, count)).sort((a, b) => a - b);
                        const mid = Math.floor(count / 2);
                        value = count % 2 === 0
                            ? (sortedSlice[mid - 1] + sortedSlice[mid]) / 2
                            : sortedSlice[mid];
                        break;
                }
            }

            row[bx] = value;
        }
        bucketedElevation[by] = row;
    }

    const processedData = {
        width: bucketedWidth,
        height: bucketedHeight,
        elevation: bucketedElevation,
        stats: rawElevationData.stats,
        bucketSizeMetersX: bucketSizeMetersX, // Physical size for rendering
        bucketSizeMetersY: bucketSizeMetersY
    };

    const duration = (performance.now() - startTime).toFixed(2);
    const reduction = (100 * (1 - (bucketedWidth * bucketedHeight) / (width * height))).toFixed(1);

    return processedData;
}


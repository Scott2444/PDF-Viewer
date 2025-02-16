'use client';

import React, { useState, useEffect } from 'react';
import { Worker, Viewer, SpecialZoomLevel, ZoomEvent } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { 
  highlightPlugin, 
  RenderHighlightTargetProps,
  RenderHighlightsProps,
} from '@react-pdf-viewer/highlight';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import '@react-pdf-viewer/highlight/lib/styles/index.css';
import * as pdfjs from 'pdfjs-dist';

// Update the worker URL to match the version
const workerUrl = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PdfViewerProps {
  url: string;
  extractedData?: Array<{ text: string; bbox: number[]; page: number }>;
  selectedText?: string | null;
}

const PdfViewer = ({ url, extractedData = [], selectedText }: PdfViewerProps) => {
  const [highlights, setHighlights] = useState<any[]>([]);
  const [pageHeights, setPageHeights] = useState<number[]>([]);
  const [zoomLevel, setZoomLevel] = useState<number>(1); // Track zoom level

  // Debug: Log when highlights are updated
  useEffect(() => {
    console.log('Highlights updated:', highlights);
  }, [highlights]);

  // Debug: Log when pageHeights are updated
  useEffect(() => {
    console.log('Page heights updated:', pageHeights);
  }, [pageHeights]);

  // Convert extractedData to the format expected by the highlight plugin
  useEffect(() => {
    if (selectedText && extractedData.length > 0 && pageHeights.length > 0) {
      const newHighlights = extractedData
        .filter((item) => item.text === selectedText)
        .map((item) => {
          const [left, top, right, bottom] = item.bbox;
  
          // Ensure the bounding box is valid
          const x1 = Math.min(left, right);
          const x2 = Math.max(left, right);
          const y1 = Math.min(top, bottom);
          const y2 = Math.max(top, bottom);
  
          return {
            id: `highlight-${item.page}-${item.bbox.join('-')}`,
            pageIndex: item.page,
            rects: [{
              x1: x1,
              y1: y1,
              x2: x2,
              y2: y2,
              width: x2 - x1,
              height: y2 - y1,
            }],
            content: {
              text: item.text,
            },
          };
        });
  
      setHighlights(newHighlights);
    } else {
      setHighlights([]);
    }
  }, [extractedData, selectedText, pageHeights]);

  // Initialize plugins
  const defaultLayoutPluginInstance = defaultLayoutPlugin();
  const highlightPluginInstance = highlightPlugin({
    renderHighlightTarget: (props: RenderHighlightTargetProps) => {
      // console.log('renderHighlightTarget called with props:', props);
      return <></>;
    },
    renderHighlights: (props: RenderHighlightsProps) => {
      // console.log('renderHighlights called with props:', props);
      return (
        <div>
          {highlights
            .filter((highlight) => highlight.pageIndex === props.pageIndex)
            .map((highlight, index) => (
              <div key={index}>
                {highlight.rects.map((rect: any, rectIndex: number) => (
                  <div
                    key={rectIndex}
                    style={{
                      background: 'rgba(255, 0, 0, 0.2)',
                      border: '1px solid rgba(255, 0, 0, 0.5)',
                      position: 'absolute',
                      left: `${rect.x1 * zoomLevel}px`, // Scale x-coordinate
                      top: `${rect.y1 * zoomLevel}px`, // Scale y-coordinate
                      width: `${rect.width * zoomLevel}px`, // Scale width
                      height: `${rect.height * zoomLevel}px`, // Scale height
                      pointerEvents: 'none',
                      zIndex: 1,
                    }}
                  />
                ))}
              </div>
            ))}
        </div>
      );
    },
  });

  // Handle document load to get page dimensions
  const handleDocumentLoad = (pdfDoc: any) => {
    console.log('Document loaded:', pdfDoc);

    // Access numPages correctly
    const numPages = pdfDoc.doc.numPages;
    console.log('Number of pages:', numPages);

    const promises = [];
    for (let i = 1; i <= numPages; i++) { // Page numbers start from 1
      promises.push({ pageIndex: i - 1, height: 792 }); // Hardcoded height for now
    }

    Promise.all(promises).then((pageData) => {
      const heights = pageData.sort((a, b) => a.pageIndex - b.pageIndex).map((p) => p.height);
      console.log('All page heights:', heights);
      setPageHeights(heights);
    });
  };

  // Handle zoom change
  const handleZoom = (e: ZoomEvent) => {
    const zoom = e.scale; // Extract zoom level from ZoomEvent
    console.log('Zoom level changed:', zoom);
    setZoomLevel(zoom);
  };

  return (
    <div className="h-[600px]">
      <Worker workerUrl={workerUrl}>
        <Viewer
          fileUrl={url}
          plugins={[
            defaultLayoutPluginInstance,
            highlightPluginInstance,
          ]}
          defaultScale={SpecialZoomLevel.PageFit}
          onDocumentLoad={handleDocumentLoad}
          onZoom={handleZoom} // Track zoom level
        />
      </Worker>
    </div>
  );
};

export default PdfViewer;
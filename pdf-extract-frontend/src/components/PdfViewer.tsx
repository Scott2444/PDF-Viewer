'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Worker, Viewer, SpecialZoomLevel, ZoomEvent } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin, DefaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { 
  highlightPlugin, 
  RenderHighlightTargetProps,
  RenderHighlightsProps,
} from '@react-pdf-viewer/highlight';
import { pageNavigationPlugin, PageNavigationPlugin } from '@react-pdf-viewer/page-navigation';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import '@react-pdf-viewer/highlight/lib/styles/index.css';
import '@react-pdf-viewer/page-navigation/lib/styles/index.css';
import * as pdfjs from 'pdfjs-dist';

// Update the worker URL to match the version
const workerUrl = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PdfViewerProps {
  url: string;
  extractedData?: Array<{id: string, text: string, bbox: number[], page: number}>;
  selectedId?: string | null;
}

const PdfViewer = ({ url, extractedData = [], selectedId }: PdfViewerProps) => {
  const [highlights, setHighlights] = useState<any[]>([]);
  const [pageHeights, setPageHeights] = useState<number[]>([]);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  
  // Create refs for plugin instances that have methods we need to access
  const pageNavigationPluginRef = useRef<PageNavigationPlugin | null>(null);

  // Initialize plugins
  const pageNavigationPluginInstance = pageNavigationPlugin();
  const defaultLayoutPluginInstance = defaultLayoutPlugin();
  const highlightPluginInstance = highlightPlugin({
    renderHighlightTarget: (props: RenderHighlightTargetProps) => {
      return <></>;
    },
    renderHighlights: (props: RenderHighlightsProps) => {
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
                      left: `${rect.x1 * zoomLevel}px`,
                      top: `${rect.y1 * zoomLevel}px`,
                      width: `${rect.width * zoomLevel}px`,
                      height: `${rect.height * zoomLevel}px`,
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

  // Store the plugin instance in the ref
  useEffect(() => {
    pageNavigationPluginRef.current = pageNavigationPluginInstance;
  }, [pageNavigationPluginInstance]);

  // Debug: Log when highlights are updated
  // useEffect(() => {
  //   console.log('Highlights updated:', highlights);
  // }, [highlights]);

  // // Debug: Log when pageHeights are updated
  // useEffect(() => {
  //   console.log('Page heights updated:', pageHeights);
  // }, [pageHeights]);

  // Convert extractedData to the format expected by the highlight plugin
  useEffect(() => {
    if (selectedId && extractedData.length > 0) {
      const selectedItem = extractedData.find((item) => item.id === selectedId);
      if (selectedItem) {
        setSelectedPage(selectedItem.page);
        
        const [left, top, right, bottom] = selectedItem.bbox;
  
        // Ensure the bounding box is valid
        const x1 = Math.min(left, right);
        const x2 = Math.max(left, right);
        const y1 = Math.min(top, bottom);
        const y2 = Math.max(top, bottom);
  
        const newHighlights = [{
          id: `highlight-${selectedItem.page}-${selectedItem.bbox.join('-')}`,
          pageIndex: selectedItem.page,
          rects: [{
            x1: x1,
            y1: y1,
            x2: x2,
            y2: y2,
            width: x2 - x1,
            height: y2 - y1,
          }],
          content: {
            text: selectedItem.text,
          },
        }];
  
        setHighlights(newHighlights);
      }
    } else {
      setHighlights([]);
      setSelectedPage(null);
    }
  }, [extractedData, selectedId]);

  // Scroll to the selected page when it changes
  useEffect(() => {
    if (selectedPage !== null && pageNavigationPluginRef.current) {
      const { jumpToPage } = pageNavigationPluginRef.current;
      if (jumpToPage) {
        jumpToPage(selectedPage);
      }
    }
  }, [selectedPage]);

  // Handle document load to get page dimensions
  const handleDocumentLoad = (pdfDoc: any) => {
    // console.log('Document loaded:', pdfDoc);

    const numPages = pdfDoc.doc.numPages;
    // console.log('Number of pages:', numPages);

    const promises = [];
    for (let i = 1; i <= numPages; i++) {
      promises.push({ pageIndex: i - 1, height: 792 });
    }

    Promise.all(promises).then((pageData) => {
      const heights = pageData.sort((a, b) => a.pageIndex - b.pageIndex).map((p) => p.height);
      console.log('All page heights:', heights);
      setPageHeights(heights);
    });
  };

  // Handle zoom change
  const handleZoom = (e: ZoomEvent) => {
    const zoom = e.scale;
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
            pageNavigationPluginInstance,
          ]}
          defaultScale={SpecialZoomLevel.PageFit}
          onDocumentLoad={handleDocumentLoad}
          onZoom={handleZoom}
        />
      </Worker>
    </div>
  );
};

export default PdfViewer;
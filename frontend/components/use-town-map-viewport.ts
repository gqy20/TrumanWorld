"use client";

import { useRef, useState, type PointerEvent, type WheelEvent } from "react";

import { SVG_H, SVG_W, clampViewBox, type ViewBox } from "./town-map-utils";

type DragState = {
  pointerId: number;
  startClientX: number;
  startClientY: number;
  originX: number;
  originY: number;
};

export function useTownMapViewport() {
  const [viewBox, setViewBox] = useState<ViewBox>({ x: 0, y: 0, width: SVG_W, height: SVG_H });
  const dragStateRef = useRef<DragState | null>(null);

  const zoomMap = (
    factor: number,
    focusX = viewBox.x + viewBox.width / 2,
    focusY = viewBox.y + viewBox.height / 2,
  ) => {
    setViewBox((current) => {
      const nextWidth = current.width * factor;
      const nextHeight = (nextWidth / SVG_W) * SVG_H;
      const ratioX = (focusX - current.x) / current.width;
      const ratioY = (focusY - current.y) / current.height;
      const nextX = focusX - nextWidth * ratioX;
      const nextY = focusY - nextHeight * ratioY;
      return clampViewBox({ x: nextX, y: nextY, width: nextWidth, height: nextHeight });
    });
  };

  const resetView = () => {
    setViewBox({ x: 0, y: 0, width: SVG_W, height: SVG_H });
  };

  const focusOnSvgPoint = (svgX: number, svgY: number) => {
    setViewBox((current) =>
      clampViewBox({
        x: svgX - current.width / 2,
        y: svgY - current.height / 2,
        width: current.width,
        height: current.height,
      }),
    );
  };

  const handlePointerDown = (event: PointerEvent<SVGSVGElement>) => {
    const target = event.target as Element;
    if (target.closest("[data-map-interactive='true']")) {
      return;
    }

    dragStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      originX: viewBox.x,
      originY: viewBox.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }

    const deltaX = ((event.clientX - dragState.startClientX) / rect.width) * viewBox.width;
    const deltaY = ((event.clientY - dragState.startClientY) / rect.height) * viewBox.height;

    setViewBox(
      clampViewBox({
        x: dragState.originX - deltaX,
        y: dragState.originY - deltaY,
        width: viewBox.width,
        height: viewBox.height,
      }),
    );
  };

  const handlePointerEnd = (event: PointerEvent<SVGSVGElement>) => {
    if (dragStateRef.current?.pointerId === event.pointerId) {
      dragStateRef.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault();

    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return;
    }

    const pointerX = ((event.clientX - rect.left) / rect.width) * viewBox.width + viewBox.x;
    const pointerY = ((event.clientY - rect.top) / rect.height) * viewBox.height + viewBox.y;
    zoomMap(event.deltaY > 0 ? 1.12 : 0.88, pointerX, pointerY);
  };

  return {
    viewBox,
    zoomMap,
    resetView,
    focusOnSvgPoint,
    handlePointerDown,
    handlePointerMove,
    handlePointerEnd,
    handleWheel,
  };
}

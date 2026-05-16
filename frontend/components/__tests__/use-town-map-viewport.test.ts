import { act, renderHook } from "@testing-library/react";

import { SVG_H, SVG_W } from "../town-map-utils";
import { useTownMapViewport } from "../use-town-map-viewport";

function svgTarget() {
  return {
    setPointerCapture: jest.fn(),
    releasePointerCapture: jest.fn(),
    getBoundingClientRect: jest.fn(() => ({
      left: 0,
      top: 0,
      width: SVG_W,
      height: SVG_H,
    })),
  };
}

describe("useTownMapViewport", () => {
  it("zooms around the current viewport center and resets to the full map", () => {
    const { result } = renderHook(() => useTownMapViewport());

    act(() => {
      result.current.zoomMap(0.85);
    });

    expect(result.current.viewBox).toEqual({
      x: 52.5,
      y: 33,
      width: 595,
      height: 374,
    });

    act(() => {
      result.current.resetView();
    });

    expect(result.current.viewBox).toEqual({ x: 0, y: 0, width: SVG_W, height: SVG_H });
  });

  it("focuses the current viewport on an svg point", () => {
    const { result } = renderHook(() => useTownMapViewport());

    act(() => {
      result.current.zoomMap(0.85);
    });
    act(() => {
      result.current.focusOnSvgPoint(600, 350);
    });

    expect(result.current.viewBox).toEqual({
      x: 302.5,
      y: 163,
      width: 595,
      height: 374,
    });
  });

  it("pans a zoomed-out viewport via pointer drag", () => {
    const { result } = renderHook(() => useTownMapViewport());
    const currentTarget = svgTarget();

    act(() => {
      result.current.zoomMap(1.5);
    });
    act(() => {
      result.current.handlePointerDown({
        pointerId: 7,
        clientX: 100,
        clientY: 100,
        target: { closest: jest.fn(() => null) },
        currentTarget,
      } as never);
    });
    act(() => {
      result.current.handlePointerMove({
        pointerId: 7,
        clientX: 0,
        clientY: 100,
        currentTarget,
      } as never);
    });

    expect(result.current.viewBox.x).toBe(-25);
    expect(result.current.viewBox.width).toBe(1050);

    act(() => {
      result.current.handlePointerEnd({
        pointerId: 7,
        currentTarget,
      } as never);
    });

    expect(currentTarget.releasePointerCapture).toHaveBeenCalledWith(7);
  });

  it("ignores pointer down events from interactive map children", () => {
    const { result } = renderHook(() => useTownMapViewport());
    const currentTarget = svgTarget();

    act(() => {
      result.current.handlePointerDown({
        pointerId: 9,
        clientX: 100,
        clientY: 100,
        target: { closest: jest.fn(() => ({ dataset: { mapInteractive: "true" } })) },
        currentTarget,
      } as never);
    });

    expect(currentTarget.setPointerCapture).not.toHaveBeenCalled();
  });

  it("zooms around the pointer position on wheel", () => {
    const { result } = renderHook(() => useTownMapViewport());
    const currentTarget = svgTarget();
    const preventDefault = jest.fn();

    act(() => {
      result.current.handleWheel({
        clientX: 175,
        clientY: 110,
        deltaY: -1,
        preventDefault,
        currentTarget,
      } as never);
    });

    expect(preventDefault).toHaveBeenCalled();
    expect(result.current.viewBox).toEqual({
      x: 42,
      y: 26.400000000000006,
      width: 616,
      height: 387.2,
    });
  });
});

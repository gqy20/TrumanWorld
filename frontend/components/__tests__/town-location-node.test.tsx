import { fireEvent, render, screen } from "@testing-library/react";

import { getTimeOfDayStyle } from "@/lib/world-utils";

import { TownLocationNode } from "../town-location-node";
import type { PositionedLocationNode, ViewBox } from "../town-map-utils";

const node: PositionedLocationNode = {
  id: "loc-1",
  name: "Cafe",
  type: "cafe",
  x: 0,
  y: 0,
  svgX: 100,
  svgY: 120,
  capacity: 4,
  occupantCount: 1,
  occupants: [
    {
      id: "agent-1",
      name: "Mei",
      current_goal: "talk",
    },
  ],
  heat: 0.5,
};

const viewBox: ViewBox = { x: 0, y: 0, width: 700, height: 440 };

describe("TownLocationNode", () => {
  it("renders a location with agent bubble and handles clicks", () => {
    const onLocationClick = jest.fn();
    const onAgentClick = jest.fn();
    const setMapSummary = jest.fn();

    render(
      <svg>
        <TownLocationNode
          node={node}
          agentNameMap={{ "agent-1": "Mei Lin" }}
          highlightedLocationId="loc-1"
          speechBubbles={{ "agent-1": { message: "hello there", key: 1 } }}
          timeStyle={getTimeOfDayStyle("afternoon")}
          viewBox={viewBox}
          onAgentClick={onAgentClick}
          onLocationClick={onLocationClick}
          setMapSummary={setMapSummary}
        />
      </svg>,
    );

    fireEvent.click(screen.getByRole("button", { name: /Cafe/ }));
    fireEvent.click(screen.getByRole("button", { name: /Mei Lin/ }));

    expect(screen.getByText("Cafe")).toBeInTheDocument();
    expect(screen.getByText(/hello there/)).toBeInTheDocument();
    expect(onLocationClick).toHaveBeenCalledWith("loc-1");
    expect(onAgentClick).toHaveBeenCalledWith("agent-1");
    expect(setMapSummary).toHaveBeenCalledWith("Mei Lin · talk");
  });
});

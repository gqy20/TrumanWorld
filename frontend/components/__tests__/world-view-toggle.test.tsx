import { fireEvent, render, screen } from "@testing-library/react";

import { WorldViewToggle } from "@/components/world-view-toggle";

describe("WorldViewToggle", () => {
  it("exposes the active view and switches with accessible buttons", () => {
    const onToggle = jest.fn();
    render(<WorldViewToggle currentView="voxel" onToggle={onToggle} />);

    expect(screen.getByRole("group", { name: "世界视图" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "舞台视图" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "导演地图" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    fireEvent.click(screen.getByRole("button", { name: "导演地图" }));

    expect(onToggle).toHaveBeenCalledWith("svg");
  });
});

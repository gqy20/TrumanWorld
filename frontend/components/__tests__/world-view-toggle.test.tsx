import { fireEvent, render, screen } from "@testing-library/react";

import { WorldViewToggle } from "@/components/world-view-toggle";

describe("WorldViewToggle", () => {
  it("exposes the selected view and switches to the director map", () => {
    const onToggle = jest.fn();
    render(<WorldViewToggle currentView="voxel" onToggle={onToggle} />);

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

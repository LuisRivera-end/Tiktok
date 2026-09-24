import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BiReport } from "./BiReport";

describe("BiReport", () => {
  it("muestra los nombres de eventos en español y permite filtrar desde un gráfico", async () => {
    const onRegion = vi.fn();
    const user = userEvent.setup();
    render(<BiReport
      regions={[{ region: "México", events: 8, views: 3, completion_rate: 0.75, retention_minutes: 1.5 }]}
      categories={[]}
      eventTypes={[{ event_type: "complete", events: 5 }, { event_type: "hashtag_tap", events: 3 }]}
      daily={[]}
      focus={{ region: "", category: "", events: 8, views: 3, completion_rate: 0.75, retention_minutes: 1.5, early_abandon_rate: 0 }}
      region=""
      category=""
      onRegion={onRegion}
      onCategory={vi.fn()}
    />);

    expect(screen.getByText("Reproducción completa")).toBeInTheDocument();
    expect(screen.getByText("Toque en etiqueta")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /México, 75 % de progreso medio.*Filtrar/ }));
    expect(onRegion).toHaveBeenCalledWith("México");
  });
});

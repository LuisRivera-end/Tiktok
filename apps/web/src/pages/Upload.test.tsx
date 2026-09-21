import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/context/Auth";
import { saveSession } from "@/lib/session";
import { UploadPage } from "@/pages/Upload";

describe("UploadPage", () => {
  it("un viewer no llama a publicar", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    saveSession("token", {
      id: "u1",
      email: "viewer@veta.local",
      display_name: "Lía",
      role: "viewer",
      age: 21,
    });
    render(
      <MemoryRouter>
        <AuthProvider>
          <UploadPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Esta cuenta no publica");
    await userEvent.click(screen.getByRole("button", { name: "Publicar" }));
    expect(fetchMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});

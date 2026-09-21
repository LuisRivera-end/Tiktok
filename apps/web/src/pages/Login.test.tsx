import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "@/context/Auth";
import { LoginPage } from "@/pages/Login";

describe("LoginPage", () => {
  it("muestra el escenario de acceso y la cuenta de demostración", () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Veta" })).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toHaveValue("viewer@veta.local");
    expect(screen.getByRole("button", { name: "Entrar al escenario" })).toBeEnabled();
  });
});

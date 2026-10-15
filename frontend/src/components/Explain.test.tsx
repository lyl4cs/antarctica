import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Explain } from "./Explain";

const setup = () =>
  render(<Explain label="Total Blocking Time">How long the page was frozen.</Explain>);

describe("Explain", () => {
  it("is closed until asked, and names the term for screen readers", () => {
    setup();
    const btn = screen.getByRole("button", { name: "What is Total Blocking Time?" });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/How long the page was frozen/)).not.toBeInTheDocument();
  });

  it("opens on click, which is what a touch user gets instead of hover", () => {
    setup();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/How long the page was frozen/)).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  it("closes on a second click", () => {
    setup();
    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByText(/How long the page was frozen/)).not.toBeInTheDocument();
  });

  it("closes on Escape", () => {
    setup();
    fireEvent.click(screen.getByRole("button"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText(/How long the page was frozen/)).not.toBeInTheDocument();
  });

  it("closes when you click away", () => {
    setup();
    fireEvent.click(screen.getByRole("button"));
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText(/How long the page was frozen/)).not.toBeInTheDocument();
  });

  it("ties the panel to the button so it is announced", () => {
    setup();
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-describedby")).toBe(screen.getByRole("note").id);
  });
});

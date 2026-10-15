import { describe, expect, it } from "vitest";
import { allocate, analyse, project, type Debt, type Emergency, type Horizon, type Profile, type Risk } from "./plan";

const horizons: Horizon[] = [1, 3, 7, 12];
const emergencies: Emergency[] = ["none", "insufficient", "enough"];
const debts: Debt[] = ["none", "some", "significant"];
const risks: Risk[] = [1, 2, 3];

const profiles: Profile[] = horizons.flatMap((horizon) =>
  emergencies.flatMap((emergency) =>
    debts.flatMap((debt) =>
      risks.map((risk) => ({ amount: 10000, goal: "wealth" as const, horizon, emergency, debt, risk })),
    ),
  ),
);

describe("allocate", () => {
  it("sums to 100% with no negative slices for every input combination", () => {
    for (const p of profiles) {
      const slices = allocate(p);
      expect(slices.reduce((n, s) => n + s.pct, 0)).toBe(100);
      expect(slices.every((s) => s.pct > 0 && s.amount >= 0)).toBe(true);
    }
  });

  it("holds more stocks when risk is higher, all else equal", () => {
    const stocks = (risk: Risk) =>
      allocate({ ...profiles[0], horizon: 7, emergency: "enough", debt: "none", risk }).find((s) => s.bucket === "stocks")!.pct;
    expect(stocks(1)).toBeLessThan(stocks(2));
    expect(stocks(2)).toBeLessThan(stocks(3));
  });

  it("holds a bigger emergency fund when savings are missing", () => {
    const em = (emergency: Emergency) =>
      allocate({ ...profiles[0], emergency }).find((s) => s.bucket === "emergency")!.pct;
    expect(em("none")).toBeGreaterThan(em("insufficient"));
    expect(em("insufficient")).toBeGreaterThan(em("enough"));
  });
});

describe("analyse", () => {
  it("keeps score within 0-100 and rewards a stronger position", () => {
    for (const p of profiles) {
      const { score } = analyse(p);
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
    }
    const weak = analyse({ ...profiles[0], emergency: "none", debt: "significant", horizon: 1 }).score;
    const strong = analyse({ ...profiles[0], emergency: "enough", debt: "none", horizon: 12 }).score;
    expect(strong).toBeGreaterThan(weak);
  });
});

describe("project", () => {
  it("orders scenarios pessimistic <= base <= optimistic and starts at the deposit", () => {
    const [low, base, high] = project(10000, 100, 10, 2);
    expect(low[0]).toBe(10000);
    expect(low.at(-1)!).toBeLessThanOrEqual(base.at(-1)!);
    expect(base.at(-1)!).toBeLessThanOrEqual(high.at(-1)!);
    expect(low).toHaveLength(11);
  });

  it("adds contributions linearly when the return is 0%", () => {
    const [zero] = project(1000, 100, 2, 2); // moderate pessimistic rate is 0%
    expect(zero.at(-1)).toBe(1000 + 100 * 24);
  });
});

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { feed, notification } from "./notification-fixtures";
import { POLL_MS, useStaffNotifications } from "./use-staff-notifications";

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
const actions = vi.hoisted(() => ({
  loadStaffNotifications: vi.fn(),
  pollStaffNotifications: vi.fn(),
  markStaffNotificationsRead: vi.fn(),
  markAllStaffNotificationsRead: vi.fn(),
}));
const toast = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("./actions", () => actions);
vi.mock("@/components/ui/toast", () => ({ toast }));

const FIRST = notification({ urgent: false, urgent_reasons: [] });
const ARRIVED = notification({
  id: "019a0000-0000-7000-8000-000000000009",
  patient_name: "Ravi Kumar",
  created_at: "2026-10-30T07:40:00Z",
});

async function settle(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

async function nextPoll(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_MS);
  });
}

describe("live staff notifications", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
    actions.loadStaffNotifications.mockResolvedValue(feed([FIRST]));
    actions.pollStaffNotifications.mockResolvedValue({
      latest_id: FIRST.id,
      unread_count: 1,
      urgent_count: 0,
    });
    actions.markStaffNotificationsRead.mockResolvedValue({
      ok: true,
      message: "Marked as read",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads once, then only polls the totals while nothing changes", async () => {
    const { result } = renderHook(() => useStaffNotifications(true));
    await settle();
    await nextPoll();

    expect(result.current.feed?.items).toEqual([FIRST]);
    expect(actions.loadStaffNotifications).toHaveBeenCalledTimes(1);
    expect(actions.pollStaffNotifications).toHaveBeenCalledTimes(1);
    expect(router.refresh).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("puts a new item on top, refreshes the page and toasts when it is urgent", async () => {
    const { result } = renderHook(() => useStaffNotifications(true));
    await settle();
    actions.pollStaffNotifications.mockResolvedValue({
      latest_id: ARRIVED.id,
      unread_count: 2,
      urgent_count: 1,
    });
    actions.loadStaffNotifications.mockResolvedValue(feed([ARRIVED, FIRST]));

    await nextPoll();

    expect(result.current.feed?.items.map((item) => item.id)).toEqual([
      ARRIVED.id,
      FIRST.id,
    ]);
    expect(result.current.feed?.urgent_count).toBe(1);
    expect(router.refresh).toHaveBeenCalledTimes(1);
    expect(toast.error).toHaveBeenCalledTimes(1);
    expect(toast.error).toHaveBeenCalledWith(
      "Urgent: Ravi Kumar",
      expect.objectContaining({
        description: "Cannot complete: Clear liquids · Colonoscopy",
      }),
    );
  });

  it("does not toast the urgent items that were there when the page opened", async () => {
    actions.loadStaffNotifications.mockResolvedValue(feed([ARRIVED]));

    renderHook(() => useStaffNotifications(true));
    await settle();

    expect(toast.error).not.toHaveBeenCalled();
  });

  it("marks an item read before opening the patient's sheet on its tab", async () => {
    actions.loadStaffNotifications.mockResolvedValue(feed([ARRIVED]));
    const { result } = renderHook(() => useStaffNotifications(true));
    await settle();

    act(() => result.current.open(ARRIVED));
    await settle();

    expect(result.current.feed?.items[0]?.read).toBe(true);
    expect(result.current.feed?.urgent_count).toBe(0);
    expect(actions.markStaffNotificationsRead).toHaveBeenCalledWith([
      ARRIVED.id,
    ]);
    expect(router.push).toHaveBeenCalledWith(
      `/dashboard?appointment=${ARRIVED.appointment_id}&tab=timeline`,
      { scroll: false },
    );
    expect(
      actions.markStaffNotificationsRead.mock.invocationCallOrder[0],
    ).toBeLessThan(router.push.mock.invocationCallOrder[0] ?? 0);
  });

  it("asks for nothing when the role cannot see notifications", async () => {
    renderHook(() => useStaffNotifications(false));
    await settle();
    await nextPoll();

    expect(actions.loadStaffNotifications).not.toHaveBeenCalled();
    expect(actions.pollStaffNotifications).not.toHaveBeenCalled();
  });
});

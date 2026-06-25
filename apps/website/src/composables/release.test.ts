import { describe, it, expect } from "vitest";
import { detectOS, pickDesktopRelease, primaryMatchKey, type Release } from "./release";

describe("detectOS", () => {
  it("识别 macOS", () => {
    expect(detectOS("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit")).toBe("mac");
  });
  it("识别 Windows", () => {
    expect(detectOS("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit")).toBe("windows");
  });
  it("其它系统归为 other", () => {
    expect(detectOS("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit")).toBe("other");
  });
});

describe("primaryMatchKey", () => {
  it("mac → mac-arm（默认 Apple 芯片）", () => {
    expect(primaryMatchKey("mac")).toBe("mac-arm");
  });
  it("windows → windows", () => {
    expect(primaryMatchKey("windows")).toBe("windows");
  });
  it("其它系统无对应产物 → null", () => {
    expect(primaryMatchKey("other")).toBeNull();
  });
});

describe("pickDesktopRelease", () => {
  const desktop017: Release = {
    tag_name: "desktop-v0.1.7",
    assets: [
      { name: "Keeper_0.1.7_aarch64.dmg", browser_download_url: "u/arm.dmg" },
      { name: "Keeper_0.1.7_x64-setup.exe", browser_download_url: "u/win.exe" },
      { name: "Keeper_0.1.7_x64_en-US.msi", browser_download_url: "u/win.msi" },
      { name: "latest.json", browser_download_url: "u/latest.json" },
    ],
  };

  it("从混了 website 版的列表里只挑最新 desktop 正式版，解析版本号与各平台直链", () => {
    // 列表按发布时间倒序：website 版排在最前也要被跳过，取第一个 desktop-v*
    const releases: Release[] = [
      { tag_name: "website-v0.1.2", assets: [] },
      desktop017,
      { tag_name: "desktop-v0.1.6", assets: [] },
    ];
    const r = pickDesktopRelease(releases);
    expect(r?.version).toBe("0.1.7");
    expect(r?.urls["mac-arm"]).toBe("u/arm.dmg");
    expect(r?.urls.windows).toBe("u/win.exe"); // exe 优先于 msi
  });

  it("跳过预发布 / 草稿，取第一个正式 desktop 版", () => {
    const releases: Release[] = [
      { tag_name: "desktop-v0.2.0-rc.1", prerelease: true, assets: [] },
      { tag_name: "desktop-v0.1.8", draft: true, assets: [] },
      desktop017,
    ];
    expect(pickDesktopRelease(releases)?.version).toBe("0.1.7");
  });

  it("没有任何 desktop 版返回 null", () => {
    expect(pickDesktopRelease([{ tag_name: "website-v0.1.2", assets: [] }])).toBeNull();
    expect(pickDesktopRelease([])).toBeNull();
  });

  it("缺某平台产物时该平台为 null（不影响其它平台）", () => {
    const r = pickDesktopRelease([
      { tag_name: "desktop-v0.1.7", assets: [{ name: "Keeper_0.1.7_aarch64.dmg", browser_download_url: "u/arm.dmg" }] },
    ]);
    expect(r?.urls["mac-arm"]).toBe("u/arm.dmg");
    expect(r?.urls.windows).toBeNull();
  });
});

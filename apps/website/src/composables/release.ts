// 下载逻辑纯函数：按 UA 猜系统、从 GitHub releases 列表里挑出最新桌面版及其下载直链。
// 不做副作用（fetch 在 useRelease 里），便于单测。
//
// 数据源为何是「同源反代的 releases 列表」而非别的：
//   ① 不直连 api.github.com：未认证 REST 限流 60 次/小时/IP，访客浏览器裸调极易撞 403。
//      改走官网自己的 nginx 同源反代（/api/gh/releases），反代加几分钟缓存把上游请求压到远低于限流，
//      还顺带避开浏览器对 api.github.com 的跨域。dev 下由 vite proxy 转发到同一端点。
//   ② 不用 /releases/latest：monorepo 多组件（desktop / website）共用同一套 GitHub Releases，
//      `latest` 不分组件——发过 website 版后会拉到它（里面没有桌面安装包）。故取**列表**，
//      按发布时间倒序找第一个 desktop-v* 才是最新桌面版。
//   ③ 不拼版本号直链 / 不读源码版本号：直接用列表里真实资产的 browser_download_url——
//      只有「发版真成功、产物真上传」的 release 才会出现在列表里，天然不脱节
//      （规避「源码 bump 了版本但发版失败」拼出 404 直链的问题）。
export type OS = "mac" | "windows" | "other";
export type MatchKey = "mac-arm" | "windows";

const REPO = "yuebai-blast/keeper";

// 兜底页：列表还没拉到 / 拉取失败 / 非 mac·windows 系统时，引导到 Releases 页让用户自选
export const RELEASES_LATEST = `https://github.com/${REPO}/releases/latest`;

// 同源反代端点（prod→nginx 缓存反代，dev→vite proxy），上游是 GitHub REST 的 releases 列表
export const RELEASES_API = "/api/gh/releases";

// GitHub releases 列表里我们关心的字段
export interface Asset {
  name: string;
  browser_download_url: string;
}
export interface Release {
  tag_name: string;
  prerelease?: boolean;
  draft?: boolean;
  assets: Asset[];
}

export type Matched = Record<MatchKey, string | null>;
export interface DesktopRelease {
  version: string; // 裸版本号 x.y.z（tag 去掉 desktop-v 前缀）
  urls: Matched;
}

// 从 releases 列表（GitHub 默认按发布时间倒序）挑出最新的 desktop 正式版，
// 解析出版本号与各平台下载直链。直链直接取资产的 browser_download_url（真实可下载，不靠拼接）。
export function pickDesktopRelease(releases: Release[]): DesktopRelease | null {
  const r = releases.find((x) => x.tag_name.startsWith("desktop-v") && !x.prerelease && !x.draft);
  if (!r) return null;

  const find = (pred: (n: string) => boolean) =>
    r.assets.find((a) => pred(a.name.toLowerCase()))?.browser_download_url ?? null;
  const dmg = (n: string) => n.endsWith(".dmg");

  return {
    version: r.tag_name.replace(/^desktop-v/, ""),
    urls: {
      // 只出 Apple Silicon mac（aarch64）；exe（NSIS）优先、回退 msi
      "mac-arm": find((n) => dmg(n) && /(aarch64|arm64)/.test(n)),
      windows: find((n) => n.endsWith(".exe")) ?? find((n) => n.endsWith(".msi")),
    },
  };
}

export function detectOS(ua: string): OS {
  if (/Windows/i.test(ua)) return "windows";
  if (/Mac OS X|Macintosh/i.test(ua)) return "mac";
  return "other";
}

// Hero 主按钮：按系统挑默认匹配键（mac 默认 Apple 芯片）
export function primaryMatchKey(os: OS): MatchKey | null {
  if (os === "mac") return "mac-arm";
  if (os === "windows") return "windows";
  return null;
}

// 系统通知工具（尽力而为旁路）：无权限则申请，被拒/异常一律静默忽略，绝不阻断业务流程。
import {
  isPermissionGranted,
  requestPermission,
  sendNotification,
} from "@tauri-apps/plugin-notification";

/** 分组完成后弹系统通知：「《项目名》分组完成，共 N 组」。失败静默。 */
export async function notifyGroupingDone(projectName: string, groupCount: number): Promise<void> {
  try {
    let granted = await isPermissionGranted();
    if (!granted) granted = (await requestPermission()) === "granted";
    if (!granted) return;
    sendNotification({ title: "Keeper", body: `《${projectName}》分组完成，共 ${groupCount} 组` });
  } catch {
    /* 通知是尽力而为的旁路，失败忽略 */
  }
}

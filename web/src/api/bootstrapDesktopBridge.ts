import {
  getDesktopBridge,
  installDesktopBridge,
  type DesktopBridge,
  type DesktopBridgeHost,
} from './desktopBridge';
import { createStubDesktopBridge } from './stubDesktopBridge';


const STUB_QUERY_PARAM = 'desktopBridgeStub';


export function shouldEnableDesktopStub(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): boolean {
  if (host.__COMPUTER_USE_ENABLE_DESKTOP_STUB__ === true) {
    return true;
  }

  const search = host.location?.search;
  if (!search) {
    return false;
  }

  return new URLSearchParams(search).get(STUB_QUERY_PARAM) === '1';
}


export function bootstrapDesktopBridge(
  host: DesktopBridgeHost = globalThis as DesktopBridgeHost,
): DesktopBridge | null {
  const existingBridge = getDesktopBridge(host);
  if (existingBridge) {
    return existingBridge;
  }

  if (!shouldEnableDesktopStub(host)) {
    return null;
  }

  return installDesktopBridge(createStubDesktopBridge(), host);
}

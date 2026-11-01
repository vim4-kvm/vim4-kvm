// Compile on macOS; run on the HDMI source host. Does not send HID or play audio.
// list prints physical display modes; set DISPLAY_ID MODE_ID changes one mode.
// Save the current mode ID from list and explicitly restore it after a test.
import CoreGraphics
import Foundation

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

let args = CommandLine.arguments
var count: UInt32 = 0
guard CGGetOnlineDisplayList(0, nil, &count) == .success else { fail("Cannot list displays") }
var displays = [CGDirectDisplayID](repeating: 0, count: Int(count))
guard CGGetOnlineDisplayList(count, &displays, &count) == .success else { fail("Cannot read displays") }
if args.count == 4 && args[1] == "set" {
    guard let display = UInt32(args[2]), displays.contains(display),
          let modeID = UInt32(args[3]),
          let modes = CGDisplayCopyAllDisplayModes(display,
              [kCGDisplayShowDuplicateLowResolutionModes: true] as CFDictionary) as? [CGDisplayMode],
          let mode = modes.first(where: { $0.ioDisplayModeID == modeID }) else { fail("Unknown display or mode") }
    let result = CGDisplaySetDisplayMode(display, mode, nil)
    guard result == .success else { fail("Mode change failed: \(result.rawValue)") }
} else if args.count != 2 || args[1] != "list" {
    fail("Usage: hdmi-source-mode list | set DISPLAY_ID MODE_ID")
}
var rows: [[String: Any]] = []
for display in displays {
    guard let current = CGDisplayCopyDisplayMode(display),
          let modes = CGDisplayCopyAllDisplayModes(display,
              [kCGDisplayShowDuplicateLowResolutionModes: true] as CFDictionary) as? [CGDisplayMode] else { continue }
    rows.append(["display": display, "vendor": CGDisplayVendorNumber(display),
                 "model": CGDisplayModelNumber(display), "current": current.ioDisplayModeID,
                 "modes": modes.map { ["id": $0.ioDisplayModeID, "width": $0.width,
                                        "height": $0.height, "pixelWidth": $0.pixelWidth,
                                        "pixelHeight": $0.pixelHeight, "hz": $0.refreshRate] as [String: Any] }])
}
let data = try JSONSerialization.data(withJSONObject: rows, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
print()

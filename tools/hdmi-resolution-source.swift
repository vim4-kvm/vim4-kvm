// Native-pixel monochrome patterns distinguish real UHD detail from an upscale.
// Display selection is explicit; the source never changes mode or sends input.
// Build: swiftc tools/hdmi-resolution-source.swift -o /tmp/hdmi-resolution-source
import Cocoa

let arguments = CommandLine.arguments
guard arguments.count == 3, let seconds = Double(arguments[1]), seconds > 0, seconds <= 3600,
      let name = ProcessInfo.processInfo.environment["VIM4_HDMI_DISPLAY"], !name.isEmpty else {
    fatalError("Set VIM4_HDMI_DISPLAY and pass SECONDS NEW-reference.png")
}
let matches = NSScreen.screens.filter { $0.localizedName.contains(name) }
guard matches.count == 1, let screen = matches.first,
      let number = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber,
      let mode = CGDisplayCopyDisplayMode(CGDirectDisplayID(number.uint32Value)) else {
    fatalError("Select exactly one existing physical HDMI display")
}
let scale = screen.backingScaleFactor
guard Int(screen.frame.width * scale) == 3840, Int(screen.frame.height * scale) == 2160,
      mode.pixelWidth == 3840, mode.pixelHeight == 2160 else {
    fatalError("The pattern requires a native 3840x2160 backing raster; current mode is \(mode.width)x\(mode.height), pixels \(mode.pixelWidth)x\(mode.pixelHeight), scale \(scale)")
}
let output = URL(fileURLWithPath: arguments[2])
guard !FileManager.default.fileExists(atPath: output.path) else { fatalError("Reference output already exists") }
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
setbuf(stdout, nil)

class ResolutionView: NSView {
    override var isFlipped: Bool { true }
    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.setShouldAntialias(false)
        context.setAllowsAntialiasing(false)
        context.scaleBy(x: 1 / scale, y: 1 / scale)
        context.setFillColor(gray: 0.25, alpha: 1)
        context.fill(CGRect(x: 0, y: 0, width: 3840, height: 2160))
        let labels: [NSAttributedString.Key: Any] = [.font: NSFont.monospacedSystemFont(ofSize: 32, weight: .regular), .foregroundColor: NSColor.white]
        for (index, pitch) in [1, 2, 4, 8].enumerated() {
            let x = 128 + index * 896
            for (row, horizontal) in [false, true].enumerated() {
                let y = 256 + row * 896
                for line in 0..<(horizontal ? 512 : 640) {
                    context.setFillColor(gray: (line / pitch) % 2 == 0 ? 0 : 1, alpha: 1)
                    context.fill(CGRect(x: x + (horizontal ? 0 : line), y: y + (horizontal ? line : 0), width: horizontal ? 640 : 1, height: horizontal ? 1 : 512))
                }
                ("\(pitch) px \(horizontal ? "horizontal" : "vertical")" as NSString).draw(at: NSPoint(x: x, y: y - 64), withAttributes: labels)
            }
        }
    }
}

let window = NSWindow(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false, screen: screen)
window.setFrame(screen.frame, display: false)
window.level = .screenSaver
window.isReleasedWhenClosed = false
let view = ResolutionView(frame: NSRect(origin: .zero, size: screen.frame.size))
window.contentView = view
window.orderFrontRegardless()
Timer.scheduledTimer(withTimeInterval: 1, repeats: false) { _ in
    guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { fatalError("Cannot cache reference") }
    view.cacheDisplay(in: view.bounds, to: bitmap)
    guard bitmap.pixelsWide == 3840, bitmap.pixelsHigh == 2160,
          let png = bitmap.representation(using: .png, properties: [:]) else { fatalError("Reference raster is not UHD") }
    do { try png.write(to: output, options: .withoutOverwriting) } catch { fatalError("Cannot write reference: \(error)") }
    print("{\"reference\":\"\(output.lastPathComponent)\",\"width\":3840,\"height\":2160,\"backingScale\":\(scale),\"modeWidth\":\(mode.width),\"modeHeight\":\(mode.height)}")
}
Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { _ in window.close(); app.terminate(nil) }
app.run()

// Encode a frame ID into HDMI pixels; log the source draw time on the same Mac
// that runs latency-receiver.mjs. This measures software endpoints, not photons.
import Cocoa

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let duration = Double(CommandLine.arguments.dropFirst().first ?? "35") ?? 35
let moving = CommandLine.arguments.contains("--motion")
let verifyCoherence = CommandLine.arguments.contains("--verify-coherence")
guard let screen = NSScreen.screens.first(where: { $0.localizedName.contains("AML") }) else {
    fatalError("No AML HDMI display is available")
}
setbuf(stdout, nil)

class LatencyView: NSView {
    var sequence: UInt32 = 0
    override func draw(_ dirtyRect: NSRect) {
        sequence += 1
        let sourceTime = Date().timeIntervalSince1970 * 1000
        NSColor(calibratedWhite: 0.12, alpha: 1).setFill()
        bounds.fill()
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 22, weight: .regular),
            .foregroundColor: NSColor.white
        ]
        let offset = moving ? CGFloat(sequence * 5 % 48) : 0
        for row in -1...Int(bounds.height / 48) + 1 {
            let y = CGFloat(row * 48) + offset
            for col in 0..<8 {
                NSColor(calibratedHue: CGFloat((row + 100 + col) % 16) / 16,
                        saturation: 0.65, brightness: 0.6, alpha: 1).setFill()
                NSRect(x: CGFloat(col) * bounds.width / 8, y: y,
                       width: bounds.width / 8 - 3, height: 45).fill()
                ("VIM4 4K60 | Row \(row) Column \(col)" as NSString).draw(
                    at: NSPoint(x: CGFloat(col) * bounds.width / 8 + 8, y: y + 10),
                    withAttributes: attrs)
            }
        }
        // A magic byte and checksum reject partially updated or unrelated frames.
        let id = sequence & 0xffff
        let checksum = ((id >> 8) ^ (id & 255) ^ 0xa5) & 255
        let word = UInt32(0xa5000000) | (id << 8) | checksum
        NSColor.black.setFill()
        let markerHeight = bounds.height * 150 / 1080
        NSRect(x: 0, y: bounds.height - markerHeight, width: bounds.width, height: markerHeight).fill()
        let margin = bounds.width * 20 / 1920
        let cell = (bounds.width - 2 * margin) / 32
        // Matching IDs at three heights expose buffers read before capture
        // has finished writing them. All markers belong to this draw call.
        for center in (verifyCoherence ? [85.0, 540.0, 995.0] : [85.0]) {
            NSColor.black.setFill()
            NSRect(x: 0, y: bounds.height * (1 - (center + 50) / 1080),
                   width: bounds.width, height: bounds.height * 100 / 1080).fill()
            for bit in 0..<32 {
                ((word & (1 << (31 - bit))) != 0 ? NSColor.white : NSColor.black).setFill()
                NSRect(x: margin + CGFloat(bit) * cell + cell / 32,
                       y: bounds.height * (1 - (center + 40) / 1080),
                       width: cell * 15 / 16, height: bounds.height * 80 / 1080).fill()
            }
        }
        print("{\"id\":\(id),\"sourceMs\":\(sourceTime),\"drawEndMs\":\(Date().timeIntervalSince1970 * 1000)}")
    }
}

let window = NSWindow(contentRect: screen.frame, styleMask: .borderless,
                      backing: .buffered, defer: false, screen: screen)
window.setFrame(screen.frame, display: false)
window.level = .floating
window.isReleasedWhenClosed = false
let view = LatencyView(frame: NSRect(origin: .zero, size: screen.frame.size))
window.contentView = view
window.orderFrontRegardless()
let timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60, repeats: true) { _ in
    view.needsDisplay = true
}
Timer.scheduledTimer(withTimeInterval: duration, repeats: false) { _ in
    timer.invalidate()
    window.close()
    app.terminate(nil)
}
app.run()

// Read-only OCR/pixel observations of an MCP screenshot; never opens a window.
import AppKit
import Vision
let image = NSImage(contentsOfFile: CommandLine.arguments[1])!
var bounds = CGRect(origin: .zero, size: image.size)
let cg = image.cgImage(forProposedRect: &bounds, context: nil, hints: nil)!
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en-US"]
try VNImageRequestHandler(cgImage: cg).perform([request])
let rows: [[String: Any]] = (request.results ?? []).compactMap { item in
    guard let text = item.topCandidates(1).first else { return nil }
    let r = item.boundingBox
    return ["text": text.string, "x": r.minX * Double(cg.width),
            "y": (1-r.maxY) * Double(cg.height), "w": r.width * Double(cg.width),
            "h": r.height * Double(cg.height)]
}
let bitmap = NSBitmapImageRep(cgImage: cg)
var samples: [[Double]] = []
if CommandLine.arguments.count == 4 {
    let x = Int(CommandLine.arguments[2])!, y = Int(CommandLine.arguments[3])!
    for dy in -5...5 { for dx in -14...14 {
        if let color = bitmap.colorAt(x: x+dx, y: y+dy)?.usingColorSpace(.deviceRGB) {
            samples.append([Double(color.redComponent),Double(color.greenComponent),Double(color.blueComponent)])
        }
    }}
}
let data = try JSONSerialization.data(withJSONObject: ["width": cg.width, "height": cg.height,
    "items": rows, "pixels": samples], options: [.sortedKeys])
FileHandle.standardOutput.write(data)

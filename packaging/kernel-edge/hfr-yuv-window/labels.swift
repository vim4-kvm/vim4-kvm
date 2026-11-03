// MCP screenshots and clicks share the JPEG's pixel coordinate system.
import AppKit
import Vision
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNRecognizeTextRequest()
try VNImageRequestHandler(url: url).perform([request])
let image = NSBitmapImageRep(data: try Data(contentsOf: url))!
let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
    guard let label = observation.topCandidates(1).first?.string else { return nil }
    let box = observation.boundingBox
    return ["label": label, "x": Int(box.midX * Double(image.pixelsWide)),
            "y": Int((1 - box.midY) * Double(image.pixelsHigh))]
}
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: rows))

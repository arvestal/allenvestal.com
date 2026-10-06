import Foundation
import Vision
import AppKit

// usage: ocr <dir>  -> prints "filename\ttext|text|..." for each jpg
let dir = CommandLine.arguments[1]
let files = try FileManager.default.contentsOfDirectory(atPath: dir).filter { $0.hasSuffix(".jpg") }.sorted()
for f in files {
    let url = URL(fileURLWithPath: dir).appendingPathComponent(f)
    guard let img = NSImage(contentsOf: url),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    let lines = (req.results ?? []).compactMap { o -> String? in guard let s = o.topCandidates(1).first?.string else { return nil }; return String(format: "%.2f,%.2f@", o.boundingBox.midX, o.boundingBox.midY) + s }
    print("\(f)\t\(lines.joined(separator: " | "))")
}

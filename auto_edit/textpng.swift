// Draw text and images onto a transparent PNG, from a JSON spec.
// The installed FFmpeg has neither drawtext nor libass, so captions are drawn
// here with the system fonts (full Vietnamese support) and overlaid by FFmpeg.
//
// Spec: {"width", "height", "out", "background": [r,g,b,a]?,
//        "images": [{"path", "x", "y", "w", "h", "alpha"?, "shadow"?}],
//        "texts":  [{"text", "size", "weight": "regular|medium|semibold|bold",
//                    "color": [r,g,b,a], "x", "y", "align": "left|center|right",
//                    "shadow"?: true, "tracking"?: 0, "maxWidth"?: px}]}
// Coordinates are pixels from the top-left; text y is the top of the line box.
import AppKit
import Foundation

struct ImageSpec: Decodable {
    let path: String; let x: Double; let y: Double; let w: Double; let h: Double
    let alpha: Double?; let shadow: Bool?
}
struct TextSpec: Decodable {
    let text: String; let size: Double; let weight: String?; let color: [Double]
    let x: Double; let y: Double; let align: String?; let shadow: Bool?; let tracking: Double?
    let maxWidth: Double?
}
struct Spec: Decodable {
    let width: Int; let height: Int; let out: String
    let background: [Double]?; let images: [ImageSpec]?; let texts: [TextSpec]?
}

func color(_ c: [Double]) -> NSColor {
    NSColor(srgbRed: c[0], green: c[1], blue: c[2], alpha: c.count > 3 ? c[3] : 1)
}

func shadow(_ on: Bool?) -> NSShadow? {
    guard on == true else { return nil }
    let s = NSShadow()
    s.shadowColor = NSColor(white: 0, alpha: 0.55)
    s.shadowBlurRadius = 10
    s.shadowOffset = NSSize(width: 0, height: -2)
    return s
}

let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
let spec = try JSONDecoder().decode(Spec.self, from: data)

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: spec.width, pixelsHigh: spec.height,
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
let ctx = NSGraphicsContext(bitmapImageRep: rep)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx.cgContext, flipped: true)
ctx.cgContext.translateBy(x: 0, y: CGFloat(spec.height))
ctx.cgContext.scaleBy(x: 1, y: -1)

if let bg = spec.background {
    color(bg).setFill()
    NSRect(x: 0, y: 0, width: spec.width, height: spec.height).fill()
}

for im in spec.images ?? [] {
    guard let img = NSImage(contentsOfFile: im.path) else {
        FileHandle.standardError.write("cannot read \(im.path)\n".data(using: .utf8)!); exit(1)
    }
    NSGraphicsContext.saveGraphicsState()
    shadow(im.shadow)?.set()
    img.draw(in: NSRect(x: im.x, y: im.y, width: im.w, height: im.h), from: .zero,
             operation: .sourceOver, fraction: im.alpha ?? 1, respectFlipped: true, hints: nil)
    NSGraphicsContext.restoreGraphicsState()
}

let weights: [String: NSFont.Weight] = ["regular": .regular, "medium": .medium,
                                        "semibold": .semibold, "bold": .bold]
func attributed(_ t: TextSpec, size: Double) -> NSAttributedString {
    let font = NSFont.systemFont(ofSize: size, weight: weights[t.weight ?? "regular"] ?? .regular)
    var attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color(t.color),
                                                .kern: t.tracking ?? 0]
    if let s = shadow(t.shadow) { attrs[.shadow] = s }
    return NSAttributedString(string: t.text.precomposedStringWithCanonicalMapping,
                              attributes: attrs)
}

for t in spec.texts ?? [] {
    var str = attributed(t, size: t.size)
    if let mw = t.maxWidth, str.size().width > mw {  // shrink long song lists to fit
        str = attributed(t, size: t.size * mw / str.size().width)
    }
    let w = str.size().width
    let x: Double
    switch t.align ?? "left" {
    case "center": x = t.x - w / 2
    case "right": x = t.x - w
    default: x = t.x
    }
    str.draw(at: NSPoint(x: x, y: t.y))
}

NSGraphicsContext.restoreGraphicsState()
try rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: spec.out))

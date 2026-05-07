import AppKit
import Foundation

let outputPath = CommandLine.arguments.dropFirst().first ?? ""
guard !outputPath.isEmpty else {
    fputs("Missing output icon path\n", stderr)
    exit(1)
}

let size = CGSize(width: 1024, height: 1024)
let image = NSImage(size: size)
image.lockFocus()

let background = NSBezierPath(roundedRect: NSRect(origin: .zero, size: size), xRadius: 220, yRadius: 220)
NSColor(calibratedRed: 0.96, green: 0.92, blue: 0.85, alpha: 1.0).setFill()
background.fill()

let accent = NSBezierPath(roundedRect: NSRect(x: 120, y: 120, width: 784, height: 784), xRadius: 180, yRadius: 180)
NSColor(calibratedRed: 0.06, green: 0.46, blue: 0.43, alpha: 1.0).setFill()
accent.fill()

let stripe = NSBezierPath()
stripe.move(to: CGPoint(x: 220, y: 710))
stripe.line(to: CGPoint(x: 804, y: 710))
stripe.lineWidth = 64
NSColor(calibratedRed: 0.93, green: 0.68, blue: 0.31, alpha: 1.0).setStroke()
stripe.stroke()

let text = "{spot}" as NSString
let paragraph = NSMutableParagraphStyle()
paragraph.alignment = .center
let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: 190, weight: .bold),
    .foregroundColor: NSColor.white,
    .paragraphStyle: paragraph,
]
text.draw(in: NSRect(x: 110, y: 320, width: 804, height: 260), withAttributes: attributes)

image.unlockFocus()

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let data = bitmap.representation(using: .png, properties: [:])
else {
    fputs("Could not render icon image\n", stderr)
    exit(1)
}

let outputURL = URL(fileURLWithPath: outputPath)
try data.write(to: outputURL)

import Cocoa

class HUDWindow: NSPanel {
    init(title: String, subtitle: String, isGreen: Bool) {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let width: CGFloat = 280
        let height: CGFloat = 80
        let x = screen.maxX - width - 24
        let y = screen.maxY - height - 24
        let rect = NSRect(x: x, y: y, width: width, height: height)

        super.init(
            contentRect: rect,
            styleMask: [.nonactivatingPanel, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )

        self.isOpaque = false
        self.backgroundColor = .clear
        self.level = .floating
        self.hasShadow = true
        self.isReleasedWhenClosed = false
        self.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        let visualEffect = NSVisualEffectView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        visualEffect.material = .hudWindow
        visualEffect.state = .active
        visualEffect.wantsLayer = true
        visualEffect.layer?.cornerRadius = 18
        visualEffect.layer?.masksToBounds = true
        visualEffect.layer?.borderColor = isGreen ? NSColor.systemGreen.withAlphaComponent(0.6).cgColor : NSColor.systemRed.withAlphaComponent(0.6).cgColor
        visualEffect.layer?.borderWidth = 1.5

        // Dot indicator
        let dot = NSTextField(labelWithString: isGreen ? "🟢" : "🛑")
        dot.frame = NSRect(x: 18, y: 22, width: 36, height: 36)
        dot.font = NSFont.systemFont(ofSize: 26)

        // Title
        let titleLabel = NSTextField(labelWithString: title)
        titleLabel.frame = NSRect(x: 58, y: 40, width: 205, height: 24)
        titleLabel.font = NSFont.systemFont(ofSize: 15, weight: .bold)
        titleLabel.textColor = .white

        // Subtitle
        let subLabel = NSTextField(labelWithString: subtitle)
        subLabel.frame = NSRect(x: 58, y: 18, width: 205, height: 20)
        subLabel.font = NSFont.systemFont(ofSize: 12, weight: .regular)
        subLabel.textColor = NSColor.white.withAlphaComponent(0.75)

        visualEffect.addSubview(dot)
        visualEffect.addSubview(titleLabel)
        visualEffect.addSubview(subLabel)
        self.contentView = visualEffect
    }
}

let args = CommandLine.arguments
let title = args.count > 1 ? args[1] : "JARVIS"
let subtitle = args.count > 2 ? args[2] : "Status changed"
let isGreen = args.count > 3 ? (args[3] == "on" || args[3] == "green" || args[3] == "true") : true

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let hud = HUDWindow(title: title, subtitle: subtitle, isGreen: isGreen)
hud.alphaValue = 0.0
hud.orderFrontRegardless()

NSAnimationContext.runAnimationGroup({ ctx in
    ctx.duration = 0.2
    hud.animator().alphaValue = 1.0
})

DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
    NSAnimationContext.runAnimationGroup({ ctx in
        ctx.duration = 0.35
        hud.animator().alphaValue = 0.0
    }, completionHandler: {
        exit(0)
    })
}

app.run()

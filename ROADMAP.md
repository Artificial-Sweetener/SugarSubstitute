# Where SugarSubstitute goes next

SugarSubstitute is already useful, but there's a lot more I want it to become. This is the direction I'm working in, not a set of dates or a queue carved in stone. Regional prompting comes first. Most of what follows can happen in whatever order makes the most sense as the work develops.

## First: regional prompting

Direct support for regional prompting is next. The canvas already gives SugarSubstitute a strong place to work with images and masks, but it needs the ability to create a blank canvas before regional prompting can feel complete. You should be able to start with an empty canvas, define or draw the masks you need, and use those regions without leaving the workspace.

I want this to feel like a natural extension of the canvas, not another stack of configuration controls bolted onto the side.

## After that, in whatever order makes sense

### Send images between workflows

Outputs are often just the starting point for the next stage. I want to let you send an image directly from one workflow's canvas into a `Load Image` node on another workflow. Generate something, send it to your inpainting workflow, and keep working without saving it, finding it again, and loading it by hand.

### Better ControlNet coverage

I haven't properly tested ControlNet yet, so I don't want to pretend its current coverage is more complete than it is. I want to put the existing paths through real use, find the rough edges and missing pieces, and add broader ControlNet support based on what actually breaks.

This one starts with an honest inventory. If you're already using ControlNet with SugarSubstitute, I'd like to hear what works and what gets in your way.

### Video that feels like part of the canvas

I want to add video support using the `python-vlc` bindings for libVLC and a new video canvas mode. The goal is to make playback and video work feel like an extension of the canvas that already works well, not a separate video application awkwardly stuffed into the same window.

The image canvas has set a high bar for how direct this should feel. Video should meet it.

### Make every platform feel more at home

I want each port to feel like it belongs on the operating system where it's running. I'm already working on a portable Mica implementation so Windows, macOS, and Linux can all enjoy the same material effects.

For macOS, I have plans for proper stoplight buttons, better window chrome, and native top-toolbar support. Linux is wonderfully less uniform, so I need help from people who actually live in its different desktop environments. Tell me what would make SugarSubstitute feel at home in GNOME, KDE Plasma, Cinnamon, XFCE, or whatever you use. I want to know which details bother you and which native behaviors matter most.

### Make Cubes execute the same way in ComfyUI

This is mostly a [SugarCubes](https://github.com/Artificial-Sweetener/SugarCubes) problem, but it matters directly to SugarSubstitute. Cubes already work in mixed ComfyUI workflows alongside ordinary nodes. What they don't yet do is execute in ComfyUI the way that same Cube arrangement executes in SugarSubstitute. Closing that gap is the goal.

The complication is that SugarCubes can't assume the ComfyUI graph contains only Cubes. The execution path has to preserve SugarSubstitute's Cube behavior while safely accounting for arbitrary non-Cube nodes around and between them. I want a Cube arrangement to mean the same thing in both places without making mixed workflows second-class citizens.

### Load an arbitrary workflow as one big Cube

I want a mode that can load an arbitrary ComfyUI workflow into SugarSubstitute as something like one big Cube. The basic idea seems straightforward: preserve the workflow, expose what can be controlled, and let SugarSubstitute treat the whole graph as one composable unit. The interesting problems will show up in real workflows, so this will need broad testing.

This should give people a useful bridge into SugarSubstitute before they have reorganized a workflow around Cubes.

### Find the Cubes already hiding in a workflow

Taking that idea further, I want SugarSubstitute to detect Cube-shaped graph segments and offer to Cube-ify them for you. A place where one graph structure ends and another begins, connected by the main data moving through the workflow, is a strong candidate for a Cube boundary.

The goal isn't to guess perfectly behind your back. It's to do the tedious structural reading, show you the likely pieces, and make turning a large graph into reusable parts much easier.

## Long goal: bring SugarSubstitute to more places

### One workflow, two views

The dream is one button in ComfyUI. You're looking at a Node Graph, wires and all. Push the button and the graph moves. Nodes fold into the sections they belong to, wires tuck themselves away, useful controls rise to the surface, and the whole thing animates into a SugarSubstitute-style Editor Panel. Push it again and the panel springs back into the graph. The nodes return, the connections draw themselves back in, and you're looking at the same workflow from the other side.

This isn't a separate simplified workflow or an export that loses the real graph. The Editor Panel and Node Graph are two views of the same live ComfyUI workflow. Changes made in either view belong to the same graph because there is only one graph.

### Start with the prompt editor

I'm already porting the prompt editor to TypeScript and Vue. It can land first as a ComfyUI node, giving you the same rich prompt editor in both places while proving that a focused part of SugarSubstitute can work naturally inside ComfyUI.

### Build the Editor Panel inside ComfyUI

The prompt editor is the first piece, not the destination. I want to port each useful editor-facing part of SugarSubstitute to reusable TypeScript and Vue components, then assemble those pieces into the alternate ComfyUI view. As that library grows, more of the graph can fold into a coherent Editor Panel until the full transformation is real.

I'm not trying to replace the native application with web code. I built SugarSubstitute as a native desktop application because that's still how I want to do serious work. The point is to let the same workflow concept exist inside ComfyUI without making people choose between the graph and the editor.

### Carry those components into a mobile application

Once those components exist, they can support a mobile application too. It would be an interface designed for its own context, but it could share SugarSubstitute's workflow language and useful editing pieces instead of starting over.

### Carry them into Photoshop

The same reusable components could power a Photoshop UXP extension, bringing SugarSubstitute's workflow concepts and the parts that belong there directly into Photoshop.

### Bring the Python components into Krita

The Python side is moving in the same direction. SugarSubstitute is becoming easier to split into useful components, which opens a path to a PyQt-based Krita extension without rebuilding everything from scratch.

This is a long goal, not one giant release. It starts with the prompt editor, grows into the ComfyUI Editor Panel one reusable piece at a time, and then gives those pieces a path into other places where they make sense.

## Long goal: grow the canvas into a photo editor

SugarSubstitute's canvas is built on [QPane](https://github.com/Artificial-Sweetener/QPane), so most of this work belongs to [QPane and its roadmap](https://github.com/Artificial-Sweetener/QPane/blob/main/ROADMAP.md). As these capabilities land there, I want SugarSubstitute to take advantage of them directly. The larger goal is a real photo-editing environment that sits inside the generation workflow instead of making you leave it.

### Real content layers

I want to cut something out of one image and paste it into another as real, editable layer content. You should be able to arrange a composite on the canvas, keep its pieces independent, and use it immediately as part of editing or inpainting.

### Adjustment layers

I want non-destructive adjustment layers for changing colors and the look of an image without baking every experiment into its pixels. They should be part of the same layer stack as the content you're editing.

### Shader layers

Shader layers should make image effects part of that stack too. Apply an effect, adjust it, move it in the layer order, or remove it without turning the original image into a chain of irreversible edits.

### Paint on the image, not only the mask

The canvas already supports drawing masks. I want full brushes and painting directly on image content, with compatibility for popular brush standards so artists don't have to abandon the tools and brush libraries they already know.

### End-to-end color management

Professional work needs more than colors that look close enough on my machine. I want full color-management support so people using calibrated displays can trust the image from load through editing, display, generation handoff, and export.

### Keep the whole thing CPU-first

QPane is becoming its own photo-editing suite, but it still needs to behave like the canvas SugarSubstitute was built around. Editing stays CPU-first so it doesn't fight inference for the GPU or choke just because you're generating in the background.

## Tell me what I'm missing

I'm interested in what the community wants SugarSubstitute to become. If one of these ideas matters to you, tell me how you'd actually use it. If something important is missing entirely, [open an issue](https://github.com/Artificial-Sweetener/SugarSubstitute/issues) and make the case for it. Specific workflows, hardware, desktop environments, and examples are especially useful.

I'm building SugarSubstitute for people who want ComfyUI's power without spending their creative time tending a graph. The best roadmap is the one that keeps making that more true.

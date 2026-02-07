import customtkinter as ctk
from bs4 import BeautifulSoup
from collections import defaultdict, deque
import heapq
import requests
import threading


class RouteGraph:
    """Graph structure storing UPSVAC airline routes.

    The graph is represented as an adjacency list:
        - Each key is a departure airport code.
        - Each value is a list of route dictionaries, where each dictionary
          represents a flight from the departure airport with:
            - dest (str): Destination airport code
            - aircraft (str): Aircraft type operating the flight
            - distance (int): Distance in nautical miles

    Provides methods to add routes to the graph structure.
    """

    def __init__(self)-> None:
        """Initialize an empty graph using defaultdict(list)."""
        self.graph = defaultdict(list)

    def add_route(self, dep: str, dest: str, aircraft: str, distance: int) -> None:
        """Add a route to the graph structure from departure to destination with aircraft and distance.

        Args:
            dep (str): Departure airport code.
            dest (str): Destination airport code.
            aircraft (str): Aircraft type operating this route.
            distance (int): Distance in nautical miles.
        """
        self.graph[dep].append({
            "dest": dest,
            "aircraft": aircraft,
            "distance": distance
        })

def fewest_legs(graph: RouteGraph, start: str, end: str, aircraft: str) -> list[str] | None:
    """Compute the route with the fewest legs using BFS (Breadth-First Search).

    BFS ensures the first path found to the destination is the one with the
    fewest number of flights (edges) because it explores all nodes at the
    current depth before moving deeper.

    Args:
        graph (RouteGraph): The graph containing all routes.
        start (str): Starting airport code.
        end (str): Destination airport code.
        aircraft (str): Aircraft type to filter flights.

    Returns:
        List[str] | None: Sequence of airport codes representing the path, or
        None if no route exists.
    """
    # Queue holds tuples of (current airport, path taken to reach it)
    queue = deque([(start, [start])])
    
    ## This set tracks visited airports to prevent cycles and redundant processing.
    visited = set()

    # dequeu is a lot quicker than using a list for BFS, as it allows O(1) pops from the front.
    while queue:
        airport, path = queue.popleft()

        # If destination reached, return immediately with the path, as BFS guarantees it's the shortest in terms of legs.
        if airport == end:
            return path

        # Skip airports we've already fully explored to avoid cycles and redundant paths.
        if airport in visited:
            continue
        visited.add(airport)

        # Explore other routes from current airport that match the aircraft type
        for edge in graph.graph[airport]:
            if edge["aircraft"] != aircraft:
                continue
            nxt = edge["dest"]
            queue.append((nxt, path + [nxt]))

    return None


def least_distance(graph: RouteGraph, start: str, end: str, aircraft: str) -> tuple[int, list[str]] | None:
    """Compute the route with the least total distance using Dijkstra's algorithm.

    Uses a priority queue (heap) to explore routes with the lowest cumulative
    distance first. In case of ties on distance, it prefers routes with fewer
    hops (legs).

    Args:
        graph (RouteGraph): Graph containing all routes.
        start (str): Starting airport code.
        end (str): Destination airport code.
        aircraft (str): Aircraft type to filter flights.

    Returns:
        tuple[int, list[str]] | None: Tuple containing total distance and
        path as a list of airport codes, or None if no route exists.
    """
    # Priority queue elements: (total_distance, number_of_hops, airport, path)
    pq = [(0, 0, start, [start])]
    
    # store best (distance, hops) seen for airport
    visited = {}

    while pq:
        dist, hops, airport, path = heapq.heappop(pq)

        # Return as soon as the destination is reached
        if airport == end:
            return dist, path

        # Skip if we've seen a better route to this airport before
        if airport in visited:
            best_dist, best_hops = visited[airport]
            if dist > best_dist:
                continue
            if dist == best_dist and hops >= best_hops:
                continue
        visited[airport] = (dist, hops)

        # Explore other routes from current airport that match the aircraft type
        for edge in graph.graph[airport]:
            if edge["aircraft"] != aircraft:
                continue

            nxt = edge["dest"]
            new_dist = dist + edge["distance"]
            new_hops = hops + 1

            heapq.heappush(pq, (new_dist, new_hops, nxt, path + [nxt]))

    return None


def parse_routes_from_string(html_text: str) -> list[dict]:
    """Parse HTML table data from UPSVAC html data that was retreived with the requests library.

    Extracts departure, destination, aircraft, and distance from the table.

    Args:
        html_text (str): HTML content of the UPSVAC all-routes page.

    Returns:
        List[dict]: List of route dictionaries with keys:
            - Departure
            - Destination
            - Aircraft
            - Distance
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", {"id": "example"})
    rows = []

    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")

        # Extract airport codes from strings like "AYPY (Jacksons International Airport)"
        departure = tds[1].get_text(strip=True).split()[0].split('(')[0]
        destination = tds[2].get_text(strip=True).split()[0].split('(')[0]
        aircraft = tds[4].get_text(strip=True)
        distance = int(tds[6].get_text(strip=True).split('nm')[0].strip())

        rows.append({
            "Departure": departure,
            "Destination": destination,
            "Aircraft": aircraft,
            "Distance": distance
        })

    return rows


def unique_list(items: list[dict]) -> list[dict]:
    """Filter a list of routes to remove duplicates and zero-distance entries.

    Uses a set to track seen routes based on all relevant keys.

    Args:
        items (list[dict]): Raw list of route dictionaries.

    Returns:
        list[dict]: Filtered list with unique, valid-distance routes.
    """
    seen = set()
    result = []
    for item in items:
        key = (item["Departure"], item["Destination"], item["Aircraft"], item["Distance"])
        if key not in seen:
            seen.add(key)

            # Ignore invalid routes with 0 distance
            if item['Distance'] == 0:
                continue
            result.append(item)
    return result



class ScrollSelect(ctk.CTkToplevel):
    """Popup window with searchable scrollable list for selecting values."""
    def __init__(self, master, title: str, values: list[str], callback):
        """Initialize the scrollable selection popup.

        Args:
            master: Parent window.
            title (str): Window title.
            values (list[str]): List of values to display.
            callback (callable): Function to call with selected value.
        """
        super().__init__(master)
        self.title(title)
        self.geometry("300x500")
        self.resizable(False, False)

        self.values = sorted(values) # Sort alphabetically
        self.callback = callback

        # Ensure popup is modal and shifts to front
        self.lift()
        self.focus_force()
        self.grab_set()

        # Search box
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="Type to filter...")
        self.search_entry.pack(fill="x", padx=10, pady=(10, 5))
        self.search_entry.bind("<KeyRelease>", self.update_list)

        # Info label (shows "top 40 results" message)
        self.info_label = ctk.CTkLabel(self, text="", text_color="gray70")
        self.info_label.pack(padx=10, pady=(0, 5))


        # Scrollable frame to hold buttons
        self.frame = ctk.CTkScrollableFrame(self)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.buttons: list[ctk.CTkButton] = []

        # Initial load of list
        self.update_list()

    def update_list(self, event=None):
        """Update the displayed list based on search query.

        Filters values by query string and limits display to top 40 results.
        """

        # Clear old buttons if there is any
        for b in self.buttons:
            b.destroy()
        self.buttons.clear()

        query = self.search_var.get().lower()

        # Filter values
        if query:
            filtered = [v for v in self.values if query in v.lower()]
        else:
            # Initial load: show only first 40 airports
            filtered = self.values[:40]
        
        # Show message if more than 40 exist
        if len(filtered) > 39:
            self.info_label.configure(text="Showing top 40 results")
        else:
            self.info_label.configure(text="")
        filtered = filtered[:40]

        # Create buttons for the items to select
        for v in filtered:
            btn = ctk.CTkButton(self.frame, text=v, command=lambda x=v: self.select(x))
            btn.pack(fill="x", pady=2)
            self.buttons.append(btn)


    def select(self, value: str):
        """Handle selection of an item and close popup."""
        self.callback(value)
        self.destroy()



class RouteFinderApp(ctk.CTk):
    """Main GUI application for UPSVAC route finding."""


    def __init__(self):
        """Initialize the main app window and UI components."""
        super().__init__()

        self.title("UPSVAC Route Finder")
        self.geometry("600x550")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.routes = []
        self.graph = RouteGraph()

        # Title
        self.label = ctk.CTkLabel(self, text="UPSVAC Route Finder", font=("Arial", 24))
        self.label.pack(pady=20)

        # Variables for user selections
        self.aircraft_var = ctk.StringVar()
        self.start_var = ctk.StringVar()
        self.end_var = ctk.StringVar()

        # Buttons for selection
        self.aircraft_button = ctk.CTkButton(self, text="Select Aircraft", width=250, command=self.pick_aircraft)
        self.start_button = ctk.CTkButton(self, text="Select Departure Airport", width=250, command=self.pick_start)
        self.end_button = ctk.CTkButton(self, text="Select Arrival Airport", width=250, command=self.pick_end)

        self.aircraft_button.pack(pady=10)
        self.start_button.pack(pady=10)
        self.end_button.pack(pady=10)

        # Compute routes button
        self.button = ctk.CTkButton(self, text="Find Routes", command=self.compute_routes)
        self.button.pack(pady=20)

        # Output box for results
        self.output = ctk.CTkTextbox(self, width=500, height=200,  font=("Courier New", 14), wrap="word")
        self.output.pack(pady=10)

        # Disable inputs until routes are loaded
        self.disable_inputs()

        # Load routes in background thread to avoid freezing UI
        threading.Thread(target=self.load_routes, daemon=True).start()


    def disable_inputs(self):
        """Disable all UI controls."""
        self.aircraft_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.end_button.configure(state="disabled")
        self.button.configure(state="disabled")

    def enable_inputs(self):
        """Enable all UI controls."""
        self.aircraft_button.configure(state="normal")
        self.start_button.configure(state="normal")
        self.end_button.configure(state="normal")
        self.button.configure(state="normal")


    def load_routes(self):
        """Fetch UPSVAC routes, parse them, and build graph.

        Runs in a background thread to keep UI responsive.
        """
        self.output.insert("end", "Loading routes from UPSVAC...\n")

        response = requests.get("https://icrew.upsvac.com/index.php/allroutes")
        self.routes = unique_list(parse_routes_from_string(response.text))

        # Add routes to graph structure for efficient pathfinding
        for r in self.routes:
            self.graph.add_route(r["Departure"], r["Destination"], r["Aircraft"], r["Distance"])

        # Build selection lists for aircraft and airports
        self.aircraft_list = sorted(set(r["Aircraft"] for r in self.routes))
        self.airport_list = sorted(set(r["Departure"] for r in self.routes) |
                                   set(r["Destination"] for r in self.routes))

        self.output.insert("end", "Routes loaded.\n")

        self.enable_inputs()

    # Selection popups
    def pick_aircraft(self):
        ScrollSelect(self, "Select Aircraft", self.aircraft_list, self.set_aircraft)

    def pick_start(self):
        ScrollSelect(self, "Select Departure Airport", self.airport_list, self.set_start)

    def pick_end(self):
        ScrollSelect(self, "Select Arrival Airport", self.airport_list, self.set_end)

    # Setters for selections
    def set_aircraft(self, value):
        self.aircraft_var.set(value)
        self.aircraft_button.configure(text=value)

    def set_start(self, value):
        self.start_var.set(value)
        self.start_button.configure(text=value)

    def set_end(self, value):
        self.end_var.set(value)
        self.end_button.configure(text=value)

    def compute_routes(self):
        """Compute and display routes based on user selection with improved formatting."""
        aircraft = self.aircraft_var.get()
        start = self.start_var.get()
        end = self.end_var.get()

        self.output.delete("1.0", "end")

        if not aircraft or not start or not end:
            self.output.insert("end", "Please select all fields.\n")
            return

        self.output.insert("end", f"Calculating routes for aircraft: {aircraft}\n")
        self.output.insert("end", f"From {start} → {end}\n\n")

        # Compute BFS (fewest legs) and Dijkstra (least distance) routes
        fl = fewest_legs(self.graph, start, end, aircraft)
        ld = least_distance(self.graph, start, end, aircraft)

        # --- Fewest Legs Route ---
        self.output.insert("end", "=== Fewest Legs Route ===\n")
        if fl:
            self.output.insert("end", f"Number of Legs: {len(fl)-1}\n")
            self.output.insert("end", "Route:\n\n")
            self.output.insert("end"," → ".join(fl) + "\n")
        else:
            self.output.insert("end", "No route found.\n")

        self.output.insert("end", "\n")

        # --- Least Distance Route ---
        self.output.insert("end", "=== Least Distance Route ===\n")
        if ld:
            total_dist, path = ld
            self.output.insert("end", f"Total Distance: {total_dist} nm\n")
            self.output.insert("end", f"Number of Legs: {len(path)-1}\n")
            self.output.insert("end", "Route:\n\n")
            # Show each leg on its own line
            for i in range(len(path)-1):
                # Find distance for this leg
                leg_dist = next(
                    (edge['distance'] for edge in self.graph.graph[path[i]] 
                    if edge['dest'] == path[i+1] and edge['aircraft'] == aircraft),
                    0
                )
                self.output.insert("end", f"{path[i]} → {path[i+1]} ({leg_dist} nm)\n")
        else:
            self.output.insert("end", "No route found.\n")


if __name__ == "__main__":
    app = RouteFinderApp()
    app.mainloop()

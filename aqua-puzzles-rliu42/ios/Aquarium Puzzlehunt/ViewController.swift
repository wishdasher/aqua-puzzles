//
//  ViewController.swift
//  Aquarium Puzzlehunt
//
//  Created by runpeng liu on 7/2/15.
//  Copyright (c) 2015 Runpeng Liu. All rights reserved.
//

import UIKit

class ViewController: UIViewController, UIWebViewDelegate {

    @IBOutlet weak var webView: UIWebView!
    @IBOutlet weak var imageView: UIImageView!
    
    var refreshControl:UIRefreshControl!
    var requestObj = NSURLRequest(URL: NSURL (string: "http://72.29.29.198:2019/aguamenti")!);
    
    let screenSize: CGRect = UIScreen.mainScreen().bounds
    
    override func viewDidLoad() {
        super.viewDidLoad()
        // Do any additional setup after loading the view, typically from a nib.
        //UIView.setAnimationsEnabled(false)
        
        setImagePortrait()
        
        self.webView.delegate = self
        self.webView.loadRequest(requestObj);

        self.refreshControl = UIRefreshControl()
        self.refreshControl.addTarget(self, action: "refresh:", forControlEvents: UIControlEvents.ValueChanged)
        self.webView.scrollView.addSubview(refreshControl)
    }

    override func didReceiveMemoryWarning() {
        super.didReceiveMemoryWarning()
        // Dispose of any resources that can be recreated.
    }
    
    func refresh(sender:UIRefreshControl) {
        let resultsURL = NSURL (string: "http://72.29.29.198:2019/aguamenti");
        let requestObj = NSURLRequest(URL: resultsURL!);
        self.webView.loadRequest(requestObj);
        sender.endRefreshing()
    }
    
    func webViewDidFinishLoad(webView: UIWebView) {
        UIView.animateWithDuration(2.0, delay: 0, options: UIViewAnimationOptions.CurveEaseIn, animations: {
            self.webView.alpha = 1.0
        }, completion: nil)
        UIView.animateWithDuration(1.5, delay: 0, options: UIViewAnimationOptions.CurveEaseOut, animations: {
            self.imageView.alpha = 0
        }, completion: nil)
    }
    
    func setImagePortrait() {
        var screenWidth = screenSize.width
        var screenHeight = screenSize.height
        
        if (screenHeight == 667) {
            // iPhone 6
            imageView.image = UIImage(named: ("Default-667h@2x") )
        } else if (screenHeight == 568) {
            // iPhone 5
            imageView.image = UIImage(named: ("Default-568h@2x") )
        } else if (screenHeight < 568) {
            // iPhone 4
            imageView.image = UIImage(named: ("Default@2x") )
        } else if (screenHeight > 667) {
            // iPad
            imageView.image = UIImage(named: ("Default-Portrait@2x") )
        }
    }

}


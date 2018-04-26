import { AfterViewInit, Component, ElementRef, Input, ViewChild } from '@angular/core';
import { NavController } from 'ionic-angular';

/**
 * Generated class for the BbNavComponent component.
 *
 * See https://angular.io/api/core/Component for more info on Angular
 * Components.
 */
@Component({
  selector: 'bb-nav',
  templateUrl: 'bb-nav.html'
})
export class BbNavComponent implements AfterViewInit {
  navItems: string[] = [
    'Personal Data',
    'Services',
    'Worktime',
    'Summary'
  ];
  @Input() activePageIndex: number;
  @ViewChild('navEl') navEl: ElementRef;

  constructor(public navCtrl: NavController) {
  }

  ngAfterViewInit(): void {
    this.scrollToActive();
  }

  scrollToActive(): void {
    const elChildren = this.navEl.nativeElement.children;
    for (let i = 0; i < elChildren.length; i++) {
      const curChild = elChildren[i];
      if (curChild.className.indexOf('active') >= 0 && i !== 0) {
        this.navEl.nativeElement.style.marginLeft = `${-curChild.offsetLeft + 15}px`;
      }
    }
  }
}
